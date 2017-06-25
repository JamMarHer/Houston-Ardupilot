import json
import os
import sys

class ReportAnalyzer(object):

    def __init__(self, report):
        self.report = report

    def analyze(self):
        counts = {'PTP': {}, 'MPTP': {}, 'Extraction': {}}
        count = 0
        for report in self.report['Reports']:
            count += 1
            counts[self.report['Reports'][report]['MissionType']][report] = self.report['Reports'][report]

        print 'PTP:        {}'.format(len(counts['PTP']))
        print 'MPTP:       {}'.format(len(counts['MPTP']))
        print 'Extraction: {}'.format(len(counts['Extraction']))
        print '---------------'
        print 'Total:      {}'.format(count)
