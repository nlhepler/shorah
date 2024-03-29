#!/usr/bin/env python

# Copyright 2007, 2008, 2009
# Niko Beerenwinkel,
# Nicholas Eriksson,
# Moritz Gerstung,
# Lukas Geyrhofer,
# Osvaldo Zagordi,
# ETH Zurich

# This file is part of ShoRAH.
# ShoRAH is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# ShoRAH is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with ShoRAH.  If not, see <http://www.gnu.org/licenses/>.

import sys
import os

import logging
import logging.handlers

# Make a global logging object.
declog = logging.getLogger("DecLog")

#################################################
# a common user should not edit above this line #
#################################################
# parameters not controlled by command line options
fasta_length    = 60    # controls line length in fasta files
win_min_ext     = 0.85  # if the read covers at least win_min_ext of the window, fill it with Ns
hist_fraction   = 0.20  # fraction that goes into the history
min_quality     = 0.9   # quality under which discard the correction
min_x_thresh    = 10    # threshold of X in the correction
max_proc        = 6     # number of processors to use in parallel (None => all available)
init_K          = 20    # initial number of clusters in diri_sampler

# set logging level
declog.setLevel(logging.DEBUG)
#################################################
# a common user should not edit below this line #
#################################################

# This handler writes everything to a file.
LOG_FILENAME = './dec.log'
hl = logging.handlers.RotatingFileHandler(LOG_FILENAME, 'w', maxBytes=100000, backupCount=5)
f = logging.Formatter("%(levelname)s %(asctime)s %(funcName)s %(lineno)d %(message)s")
hl.setFormatter(f)
declog.addHandler(hl)

to_correct = {}
correction = {}
quality = {}

count = {}
count['A'] = 0
count['C'] = 0
count['G'] = 0
count['T'] = 0
count['X'] = 0
count['-'] = 0
clusters  = [ [] ]
untouched = [ [] ]

win_shifts = 3
keep_all_files  = False

def gzip_file(f_name):
    '''Gzip a file and return the name of the gzipped, removing the original
    '''
    import gzip
    f_in = open(f_name, 'rb')
    f_out = gzip.open(f_name + '.gz', 'wb')
    f_out.writelines(f_in)
    f_out.close()
    f_in.close()
    os.remove(f_in.name)

    return f_out.name

def parse_aligned_reads(reads_file):
    """
    Parse reads from a file with aligned reads in fasta format
    """
    out_reads = {}

    if not os.path.isfile(reads_file):
        declog.error('There should be a file here: ' + reads_file)
        sys.exit('There should be a file here: ' + reads_file)
    else:
        declog.info( 'Using file ' + reads_file + ' of aligned reads')

    handle = open(reads_file)
    declog.debug('Parsing aligned reads')

    for h in handle:
        name, start, stop, mstart, mstop, this_m = h.rstrip().split('\t')
        out_reads[name] = [ None, None, None, None, [] ]
        out_reads[name][0] = int(start) #
        out_reads[name][1] = int(stop) #
        out_reads[name][2] = int(mstart) # this is
        out_reads[name][3] = int(mstop)  # this too
        out_reads[name][4] = this_m

    return out_reads

def windows(run_settings):
    """run b2w to make windows from bam
    """

    import subprocess
    bam, fasta, w, i, m, x, reg = run_settings
    dn = os.path.dirname(__file__)
    my_prog = os.path.join(dn, 'b2w')
    my_arg = ' -w %i -i %i -m %i -x %i %s %s %s' % (w, i, m, x, bam, fasta, reg)

    try:
        retcode = subprocess.call(my_prog + my_arg, shell=True)
        if retcode < 0:
            declog.error('%s %s' % (my_prog, my_arg))
            declog.error('b2w returned %i' % retcode)
        else:
            declog.debug('Finished making windows')
            declog.debug('b2w returned %i' % retcode)
    except OSError, ee:
        declog.error('Execution of b2w failed: %s' % ee)
    return retcode


def run_dpm(run_setting):
    """run the dirichlet process clustering
    """

    import subprocess
    filein, j, a = run_setting
    dn = os.path.dirname(__file__)
    my_prog = os.path.join(dn, 'diri_sampler')
    my_arg =  ' -i %s -j %i -t %i -a %f -K %d' % (filein, j, int(j*hist_fraction), a, init_K)

    try:
        #os.remove('./corrected.tmp' )
        os.remove('./assignment.tmp')
    except:
        pass

    # runs the gibbs sampler for the dirichlet process mixture
    try:
        retcode = subprocess.call(my_prog + my_arg, shell=True)
        if retcode < 0:
            declog.error('%s %s' % (my_prog, my_arg))
            declog.error('Child diri_sampler was terminated by signal %d' % -retcode)
        else:
            declog.debug('run %s finished' % my_arg)
            declog.debug('Child diri_sampler returned %i' % retcode)
    except OSError, ee:
        declog.error('Execution of diri_sampler failed: %s' % ee)

    return


def correct_reads(chr, wstart, wend):
    ''' Parses corrected reads (in fasta format) and correct the reads
    '''
    # out_reads[match_rec.id][0] = qstart
    # out_reads[match_rec.id][1] = qstop
    # out_reads[match_rec.id][2] = mstart
    # out_reads[match_rec.id][3] = mstop
    # out_reads[match_rec.id][4] = Sequence...

    from Bio import SeqIO
    import gzip
    try:
        if os.path.exists('corrected/w-%s-%s-%s.reads-cor.fas.gz' % (chr, wstart, wend)):
            cor_file = 'corrected/w-%s-%s-%s.reads-cor.fas.gz' % (chr, wstart, wend)
            handle = gzip.open(cor_file)
        else:
            cor_file = 'w-%s-%s-%s.reads-cor.fas' % (chr, wstart, wend)
            handle = open(cor_file, 'rb')

        for seq_record in SeqIO.parse(handle, 'fasta'):
            assert '\0' not in seq_record.seq.tostring(), 'binary file!!!'
            read_id = seq_record.id # read_name_rule.search(seq_record.id).group(1)
            try:
                correction[read_id][wstart] = list( seq_record.seq.tostring() )
                quality[read_id][wstart] = float(seq_record.description.split('|')[1].split('=')[1])
                assert quality[read_id][wstart] <= 1.0, 'try: quality must be < 1, %s' % cor_file
            except KeyError:
                correction[read_id] = {}
                quality[read_id] = {}
                correction[read_id][wstart] = list( seq_record.seq.tostring() )
                quality[read_id][wstart] = float(seq_record.description.split('|')[1].split('=')[1])
                assert quality[read_id][wstart] <= 1.0, 'except: quality must be < 1, %s' % cor_file
        handle.close()
        return
    except IOError:
        declog.warning('No reads in window %s?' % wstart)
        return


def get_prop(filename):
    """
    fetch the number of proposed clusters from .dbg file
    """
    import gzip
    try:
        if not os.path.exists(filename):
            filename = 'debug/%s.gz' % filename
            h = gzip.open(filename, 'rb')
        else:
            h = open(filename)
        for l in h:
            if l.startswith('#made'):
                prop = int(l.split()[1])
                break
        h.close()
        return prop
    except:# IOError, UnboundLocalError:
        return 'not found'


def base_break(baselist):
    """
    """
    import random

    for c1 in count:
        count[c1] = 0
    for c in baselist:
        if c.upper() != 'N':
            count[c.upper()] += 1

    maxm = 0
    out = []
    for b in count:
        if count[b] >= maxm:
            maxm = count[b]
    for b in count:
        if count[b] == maxm:
            out.append(b)

    rc = random.choice(out)

    return rc

def win_to_run(alpha):
    '''returns windows to run on diri_sampler
    '''
    rn_list = []
    try:
        file=open('coverage.txt')
    except IOError:
        sys.exit('Coverage file generated by b2w not found.')

    for f in file:
        winFile, chr, beg, end, cov = f.rstrip().split('\t')
        j=int(cov)*15
        if j > 300000:
            j=300000
        stem = winFile.split('-reads')[0]
        fstgz = 'raw_reads/%s-reads.gz' % stem
        corgz = 'corrected/%s-reads-cor.fas.gz' % stem
        if os.path.exists(corgz):
            continue
        else:
            rn_list.append((winFile,j,alpha))
            if os.path.exists(winFile):
                continue
            elif os.path.exists(fstgz):
                shutil.move('raw_reads/%s-reads.gz' % stem, './')
                subprocess.check_call(["gunzip", "%s-reads.gz" % stem])

    return rn_list


def main(in_bam, in_fasta, step, win_shifts, max_coverage, sigma, region, keep_all_files, alpha):
    '''
    Performs the error correction analysis, running diri_sampler
    and analyzing the result
    '''
    from multiprocessing import Pool
    import shutil
    import glob

    if step % win_shifts != 0:
        sys.exit('Window size must be divisible by win_shifts')

    if win_min_ext < 1/float(win_shifts):
        declog.warning('Warning: some bases might not be covered by any window')

    if max_coverage/step < 1:
        sys.exit('Please increase max_coverage')

    incr = step/win_shifts
    max=max_coverage/step

    if not os.path.isfile(in_bam):
        sys.exit("File '%s' not found" % in_bam)

    if not os.path.isfile(in_fasta):
        sys.exit("File '%s' not found" % in_fasta)

    #run b2w
    retcode = windows((in_bam, in_fasta, step, incr, win_min_ext*step, max, region))
    if retcode is not 0:
        sys.exit()

    aligned_reads = parse_aligned_reads('reads.fas')
    r = aligned_reads.keys()[0]
    gen_length = aligned_reads[r][1] - aligned_reads[r][0]

    if step > gen_length:
        sys.exit('The window size must be smaller than the genome region')

    declog.info('%s reads are being considered' %  len(aligned_reads))

    for k in aligned_reads.keys():
        to_correct[k] = [None, None, None, None, []]
        to_correct[k][0] = aligned_reads[k][0]
        to_correct[k][1] = aligned_reads[k][1]
        to_correct[k][2] = aligned_reads[k][2]
        to_correct[k][3] = aligned_reads[k][3]
        to_correct[k][4] = [] # aligned_reads[k][4][:]

    ############################################
    # Now the windows and the error correction #
    ############################################


    runlist = win_to_run(alpha)

    # run diri_sampler on all available processors
    pool = Pool(processes=max_proc)
    pool.map(run_dpm, runlist)

    # prepare directories
    if keep_all_files:
        for sd_name in ['debug', 'sampling', 'freq', 'support', 'corrected', 'raw_reads']:
            try:
                os.mkdir(sd_name)
            except OSError:
                pass

    # parse corrected reads
    proposed= {}
    for i in runlist:
        winFile, j, a = i
        parts=winFile.split('-')
        chr=parts[1]
        beg=parts[2]
        end=parts[3].split('.')[0]
        declog.info('reading windows for start position %s' % beg)
        correct_reads(chr, beg, end)
        stem = 'w-%s-%s-%s' % (chr, beg, end)
        declog.info('this is window %s' % stem)
        dbg_file = stem + '.dbg'
        # if os.path.exists(dbg_file):
        proposed[beg] = (get_prop(dbg_file), j)
        declog.info('there were %s proposed' % str(proposed[beg][0]))

    # (re)move intermediate files
    if not keep_all_files:
        tr_files = glob.glob('./w*reads.fas')
        tr_files.extend(glob.glob('./*.smp'))
        tr_files.extend(glob.glob('./w*.dbg'))
        for trf in tr_files:
            os.remove(trf)

        tr_files = glob.glob('./w*reads-cor.fas')
        tr_files.extend(glob.glob('./w*reads-freq.csv'))
        tr_files.extend(glob.glob('./w*reads-support.fas'))
        for trf in tr_files:
            if os.stat(trf).st_size == 0:
                os.remove(trf)
    else:
        for dbg_file in glob.glob('./w*dbg'):
            if os.stat(dbg_file).st_size > 0:
                gzf = gzip_file(dbg_file)
                try:
                    os.remove('debug/%s' % gzf)
                except OSError:
                    pass
                shutil.move(gzf, 'debug/')
            else:
                os.remove(dbg_file)

        for smp_file in glob.glob('./w*smp'):
            if os.stat(smp_file).st_size > 0:
                gzf = gzip_file(smp_file)
                try:
                    os.remove('sampling/%s' % gzf)
                except OSError:
                    pass
                shutil.move(gzf, 'sampling/')
            else:
                os.remove(smp_file)

        for cor_file in glob.glob('./w*reads-cor.fas'):
            if os.stat(cor_file).st_size > 0:
                gzf = gzip_file(cor_file)
                try:
                    os.remove('corrected/%s' % gzf)
                except OSError:
                    pass
                shutil.move(gzf, 'corrected/')
            else:
                os.remove(cor_file)

        for sup_file in glob.glob('./w*reads-support.fas'):
            if os.stat(sup_file).st_size > 0:
                gzf = gzip_file(sup_file)
                try:
                    os.remove('support/%s' % gzf)
                except OSError:
                    pass
                shutil.move(gzf, 'support/')
            else:
                os.remove(sup_file)

        for freq_file in glob.glob('./w*reads-freq.csv'):
            if os.stat(freq_file).st_size > 0:
                gzf = gzip_file(freq_file)
                try:
                    os.remove('freq/%s' % gzf)
                except OSError:
                    pass
                shutil.move(gzf, 'freq/')
            else:
                os.remove(freq_file)

        for raw_file in glob.glob('./w*reads.fas'):
            if os.stat(raw_file).st_size > 0:
                gzf = gzip_file(raw_file)
                try:
                    os.remove('raw_reads/%s' % gzf)
                except OSError:
                    pass
                shutil.move(gzf, 'raw_reads/')
            else:
                os.remove(raw_file)


    ############################################
    ##      Print the corrected reads         ##
    ##
    ## correction[read_id][wstart] = sequence ##
    ## quality[read_id][wstart] = posterior   ##
    # ##########################################
    reason = [0, 0, 0]
    declog.info('now correct')

    creads = 0
    storestore = []
    for r in to_correct:
        if r not in correction.keys():
            continue
        creads += 1
        if creads % 500 == 0:
            declog.info('considered %d corrected reads' % creads)
        rlen = len(aligned_reads[r][4]) # length of original read
        rst = aligned_reads[r][2] # read start in the reference

        corrstore = []
        for rpos in range(rlen):
            this = []
            for cst in correction[r]:
                tp = rpos + rst - int(cst)
                if tp < 0:
                    reason[0] = reason[0] + 1
                if tp >= len(correction[r][cst]):
                    reason[1] = reason[1] + 1
                if tp >= 0 and tp < len(correction[r][cst]) and quality[r][cst] > min_quality:
                    reason[2] = reason[2] + 1
                    tc = correction[r][cst][tp]
                    this.append(tc)
                    corrstore.append(rpos)

            if len(this) > 0: cb = base_break(this)
            else: cb = 'X'
            to_correct[r][4].append(cb)
            del this
    ##     ccst = []
    ##     for i in range(rlen):
    ##         if i not in corrstore: ccst.append(i)
    ##     if len(ccst) > 50:
    ##         print aligned_reads[r]
    ##         print ccst
    ##         print correction[r]
    ##         sys.exit()
    ##     print ccst
    ##     storestore.append(len(ccst))
    ## print storestore

   # print reason
    ccx = {}
    cin_stem = os.path.split(in_bam)[1].split('.')[0]
    fch = open('%s.cor.fas' % cin_stem, 'w')
    for r in to_correct:
        cor_read = ''.join(to_correct[r][4])
        init_x = len(cor_read.lstrip('-')) - len(cor_read.lstrip('-X'))
        fin_x = len(cor_read.rstrip('-')) - len(cor_read.rstrip('-X'))
        cx = to_correct[r][4].count('X') - init_x - fin_x
        ccx[cx] = ccx.get(cx, 0) + 1
        if cx <= min_x_thresh and cor_read.lstrip('-X') != '':
            fch.write('>%s %d\n' % (r, to_correct[r][2] + init_x - to_correct[r][0]))
            cc = 0
            for c in cor_read.lstrip('-X'):
                if c != 'X':
                    fch.write(str(c))
                    fch.flush()
                    cc = cc + 1
                    if cc % fasta_length == 0:
                        fch.write('\n')

            if cc % fasta_length != 0:
                fch.write('\n')
    fch.close()

 #   for k, v, in ccx.items():
  #      print k, v

    # write proposed_per_step to file
    ph = open('proposed.dat', 'w')
    ph.write('#base\tproposed_per_step\n')
    for kp in sorted(proposed.iterkeys()):
        if proposed[kp][0] != 'not found':
            ph.write('%s\t%f\n' % (kp, float(proposed[kp][0])/proposed[kp][1]))
    ph.close()

if __name__ == "__main__":

    import optparse
    # parse command line
    optparser = optparse.OptionParser()

    optparser.add_option("-b", "--bam", help="file with aligned reads <.bam format>",
                         default="", type="string", dest="b")
    optparser.add_option("-f", "--fasta", help="reference genome in fasta format.",
                         default="", type="string", dest="f")
    optparser.add_option("-a", "--alpha", help="alpha in dpm sampling <0.01>",
                         default=0.01, type="float", dest="a")
    optparser.add_option("-w", "--windowsize", help="window size <201>",
                         default=201, type="int", dest="w")
    optparser.add_option("-s", "--winshifts", help="number of window shifts <3>",
                         default=3, type="int", dest="s") # window shifts, such that each base is covered up to win_shifts times
    optparser.add_option("-i", "--sigma", help="value of sigma to use when calling SNVs", default=0.01,
                         type="string", dest="i")
    optparser.add_option("-x", "--maxcov", help="approximate maximum coverage allowed", default=10000,
                         type="int", dest="x")
    optparser.add_option("-r", "--region", help="region in format 'chr:start-stop', eg 'ch3:1000-3000'", default='',
                         type="string", dest="r")

    optparser.add_option("-k","--keep_files", help="keep all intermediate files of diri_sampler <default=False>",
                         action="store_true", dest="k", default=False)
    optparser.add_option("-t","--threshold", help="if similarity is less, throw reads away... <default=0.7>",
                         type="float", dest="threshold", default=0.7)
    optparser.add_option("-d","--delete_s2f_files",help="delete temporary align files of s2f.py <default=False>",
                         action="store_true", default=False, dest="d")
    optparser.add_option("-n","--no_pad_insert",help="do not insert padding gaps in .far file<default=insert>",
                         action="store_false", default=True, dest="pad")

    (options, args) = optparser.parse_args()

    supported_formats = {
        'bam': 'aligned reads',
        'fasta': 'reference genome'
        }
    declog.info(' '.join(sys.argv))
    # check the input file is in supported format
    try:
        tmp_filename = os.path.split(options.b)[1]
        [in_stem, in_format]  = [tmp_filename.split('.')[0], tmp_filename.split('.')[-1]]
        t = supported_formats[in_format]
    except IndexError:
        declog.error('The input file must be filestem.format')
        print 'The input file must be filestem.format'
        print 'Supported formats are'
        for sf in supported_formats.iteritems():
            print sf[0], ':', sf[1]
        sys.exit()
    except KeyError:
        declog.error('format unknown')
        print in_format, 'format unknown'
        print 'Supported formats are'
        for sf in supported_formats.iteritems():
            print sf[0], ':', sf[1]
        sys.exit()

    in_bam = options.b
    in_ref = option.f
    keep_all_files = options.k
    step = options.w
    win_shifts = options.s
    sigma = options.j
    alpha = options.a
    region = options.r
    main(in_bam, in_ref, step, win_shifts, max_coverage, sigma, region, keep_all_files, alpha)
