#!/usr/bin/env python3

import argparse
import collections
import json
import sys

import requests

RowUpdate = collections.namedtuple('update', ['columns', 'operation', 'timestamp'])

def parse(line):
    (*columns, metadata) = line.strip().split('\t')
    (diff, timestamp) = metadata.split(' at ')
    operation = 'delete' if diff.endswith('-1') else 'insert'
    return RowUpdate(columns, operation, timestamp)

def main(table):
    base_url = 'http://localhost:8875/api/v1/update/{}'.format(table)

    # Tell Tornado to clear it's internal cache
    requests.delete(base_url)

    for line in sys.stdin:
        update = parse(line)
        requests.post(base_url, json=update._asdict())

if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument('table', help='Name of table to tail')
    args = parser.parse_args()
    main(args.table)
