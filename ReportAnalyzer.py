import json
import os
import sys

class ReportAnalyzer(object):

    def __init__(self, report):
        self.report = report

    def analyze(self):
        with open("report.json") as file:
            json_file = json.load(file)
        counts = {'PTP': {}, 'MPTP': {}, 'Extraction': {}}
        count = 0
        for report in json_file['Reports']:
            count += 1
            counts[json_file['Reports'][report]['MissionType']][report] = json_file['Reports'][report]

        print 'PTP:        {}'.format(len(counts['PTP']))
        print 'MPTP:       {}'.format(len(counts['MPTP']))
        print 'Extraction: {}'.format(len(counts['Extraction']))
        print '---------------'
        print 'Total:      {}'.format(count)
