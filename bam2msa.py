#!/usr/bin/env python
import sys

import pysam

import Bio.Seq
import Bio.SeqRecord
import Bio.SeqIO
import Bio.Align.Generic
from Bio.Alphabet import IUPAC, Gapped
from Bio.Align import MultipleSeqAlignment

alphabet = Gapped(IUPAC.ambiguous_dna)
SANGER_SCORE_OFFSET = ord("!")
q_mapping = dict()
for letter in range(0,255):
    q_mapping[chr(letter)] = letter-SANGER_SCORE_OFFSET
QC = 6

def getseq(AlignedRead, start=0, stop=0, qcutoff=QC):
    """Retrieve the sequence of an AlignedRead object between start and stop
    of the reference position. The output will be padded by N's if the
    region exceeds the read length.

    """
    rpos = 0 # position in the read
    gaps = 0 # number of gaps added
    fasta = str() # will hold the alignment

    # Aligned?
    if AlignedRead.is_unmapped:
        return

    rseq = AlignedRead.seq
    pos = AlignedRead.pos
    seq = ""

    for i,s in enumerate(rseq):
        try:
            if q_mapping[AlignedRead.qual[i]] >= qcutoff:
                seq += s
            else:
                seq += 'N'
        except TypeError:
            seq += s

    ins = []
    gpos = pos
    # cigar alignment (operation, length)
    # 0 for matches, 1 for insertions, 2 for deletions
    if AlignedRead.cigar != None:
        for op in AlignedRead.cigar:
            if op[0] == 0:
                fasta += seq[rpos:(rpos+op[1])]
                rpos += op[1]
                gpos += op[1]
            elif op[0] == 1:
                if gpos - start >= 0 and gpos + op[1] < stop:
                    # genome position, insertion sequence, insertion flag
                    ins.append((gpos-start, seq[rpos:(rpos+op[1])], 0))
                rpos += op[1] # Skip the insertion
            elif op[0] == 2: # Deletion
                for i in range(op[1]):
                    fasta += 'n' #Insert gaps
                gaps += op[1]

    else:
        fasta += seq

    # Pad the ends
    for i in range(pos - start):
        fasta = 'n' + fasta
    for i in range(stop - pos - AlignedRead.rlen - gaps):
        fasta = fasta + 'n'

    # Compute range to output
    begin = max(0, start - AlignedRead.pos)
    end = stop - start + 1 + begin
    if not len(fasta[begin:end]) == end - begin:
        for i in range( end - begin - len(fasta[begin:end])):
            fasta += 'n' # Pad end because we omitted insertions
        #print fasta[begin:end]
    return fasta[begin:end], ins

def printfasta(AlignedRead, start=0, stop=0, out=sys.stdout, Nmax=0.1, qcutoff=QC):
    """
    Retrieve the sequence of an aligned read and print in fasta format.
    """
    fasta = getseq(AlignedRead, start=start, stop=stop, qcutoff=qcutoff)
    if fasta.count('N') < Nmax * len(fasta):
        print >>out, ">" + AlignedRead.qname
        print >>out, fasta
        return 1
    return 0

def getSeqRecord(AlignedRead, start=0, stop=0):
    """Get a SeqRecord object from AlignedRead between positions start and stop.
    """
    seq, ins = getseq(AlignedRead, start=start, stop=stop)
    return Bio.SeqRecord.SeqRecord(
        Bio.Seq.Seq(seq, alphabet), id=AlignedRead.qname,
        name="%s:%i-%i" % (AlignedRead.rname, start, stop),
        description="",
        annotations={
        "strand": AlignedRead.is_reverse,
        "CIGAR": AlignedRead.cigar,
        "insertions": ins,
        "pos": AlignedRead.pos}
        )

def bam2fasta(sam_name, chrom=None, start=None, stop=None, minlen=1, \
              out=sys.stdout, qcutoff=QC, strand=2):
    """Extract the reads from an samfile and print as fasta.
    """
    it = sam_name.fetch(chrom, start, stop)
    i = 0
    for read in it:
        if read.rlen - start + read.pos + 1 > minlen  and \
               stop - read.pos +1 >= minlen and \
               (strand == 2 or read.is_reverse == strand):
            i += printfasta(read, start=start, stop=stop, out=out, qcutoff=qcutoff)
    print >> sys.stderr, "[samtools] Fetched %i reads from %s:%i-%i." % \
          (i, chrom, start, stop)


def bam2Alignment(sam_name, chrom = None, start = None, stop = None, minlen = 1):
    """
    Read alignment from samfile and return Alignment object.
    """
    it = sam_name.fetch(chrom, start, stop)
    aln = MultipleSeqAlignment(alphabet)
    for read in it:
        if read.rlen - start + read.pos + 1 > minlen  and stop - read.pos +1 >= minlen:
            aln.append(getSeqRecord(read, start=start, stop=stop))

    return aln

def gap_span(reads, bases):
    '''
    Returns a MSA with rows=reads and columns=bases, composed of gaps only
    '''
    spal = MultipleSeqAlignment(alphabet)
    span = ''.join('-'*bases)
    for r in reads:
        spal.append(Bio.SeqRecord.SeqRecord(Bio.Seq.Seq(span, alphabet), id=r))
    return spal

def insert_gap(rec_seq, ins_info):
    '''
    As the name suggests...
    '''
    new_seq = list(rec_seq)
    print rec_seq
    print len(new_seq)
    for info in ins_info:
        for i, l in enumerate(info[1]):
            offset = new_seq[:info[0]].count('-')
            assert new_seq[info[0] + i + offset] == '-', \
                   'Substituting %s at %d' % \
                   (new_seq[info[0] + i + offset], info[0] + i + offset)
            new_seq[info[0] + i + offset] = l
        offset += len(info[1])

    return ''.join(new_seq).replace('n', '-')


def multAlign(aln):

    from Bio.Seq import Seq

    ins_len = {}
    ins_id = {} # stores what to insert, where and for who
    al_reads = [rec.id for rec in aln]

    # record the insertions positions for all reads
    for rec in aln:
        ins_arr = []
        if rec.annotations['insertions'] != []:
            print 'XXX', rec.annotations['insertions']
            for i in rec.annotations['insertions']:
                ins_arr.append(i)
                # in case of different insertions at the same position,
                # consider only the largest
                if i[0] not in ins_len:
                    ins_len[i[0]] = len(i[1])
                else:
                    ins_len[i[0]] = max(ins_len[i[0]], len(i[1]))
        if ins_arr != []:
            ins_id[rec.id] = ins_arr

    for k, v in ins_id.items():
        print >> sys.stderr, '-------->insertion from read ', k, ' at ', v
    # some auxiliary quantities
    s_ins = [(k, ins_len[k]) for k in sorted(ins_len)]
    cut_points = [s[0] for s in s_ins]
    cut_points.insert(0, 0)
    cut_points.append(None)

    # here we *expand* the alignment by padding with gaps
    # the positions were any read shows insertions
    edited = gap_span(al_reads, 0)
    for i, cp in enumerate(cut_points[:-1]):
        start_here = cp
        end_here = cut_points[i+1]
        edited += aln[:, start_here:end_here]
        if end_here != None: edited += gap_span(al_reads, ins_len[end_here])

    # now we can print
    for rec in edited:
        if rec.id not in ins_id:
            rec.seq = Seq(rec.seq.tostring().replace('n', '-'), alphabet)
            rec.description = '| NoInsertions'
        else:
            rec.seq = Seq(insert_gap(rec.seq, ins_id[rec.id]), alphabet)
            rec.description='| InsertionsAdded'

    return edited


if __name__ == "__main__":
    '''Main does the main
    '''
    from optparse import OptionParser

    from Bio import AlignIO

    parser = OptionParser(usage = "%prog [options] <bamfile>")
    parser.add_option("-c", '--chromosome', type = 'string', dest = 'chrom', default = None,
                      help = "Chromosome [None]")
    parser.add_option("-l", '--left-end', type = 'int', dest = 'start', default = 0,
                      help = "Left end of region [0]")
    parser.add_option("-r", '--right-end', type = 'int', dest = 'stop', default = 100,
                      help = "Right end of region [100]")
    parser.add_option("-m", '--min-length', type = 'int', dest = 'minlen', default = 50,
                      help = "Minimal length of unpadded reads [50].")
    parser.add_option("-q", '--quality-cutoff', type = 'int', dest = 'qcutoff', default = QC,
                      help = "Mask bases with quality lower than QCUTOFF by 'N'.")
    parser.add_option("-s", '--strand', type = 'int', dest = 'strand', default = 2,
                      help = "Only report alignment from strand (0: forward, 1: reverse, 2: both) [2].")
    parser.add_option("-o", '--outfile', type = 'string', dest = 'outfile', default = None,
                      help = "Print output [stdout].")

    (options, args) = parser.parse_args(sys.argv[1:])
    if len(args) != 1: parser.error("Incorrect number of arguments.")
    samfile = pysam.Samfile(args[0], 'rb')
    if options.outfile:
        outfile = open(sys.argv[2], 'w')
    else:
        outfile = sys.stdout
    # bam2fasta(samfile, chrom = options.chrom, start = options.start, stop = options.stop,
    # minlen = options.minlen, out = outfile, qcutoff=options.qcutoff, strand = options.strand)
    b2a = bam2Alignment(samfile, chrom=options.chrom,
                        start=options.start, stop=options.stop,
                        minlen=options.minlen)
    faln = multAlign(b2a)
    AlignIO.write(faln, outfile, 'fasta')
    samfile.close()
    outfile.close()
