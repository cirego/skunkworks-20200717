#!/usr/bin/env python3

import argparse
import json
import sys

import requests

def parse(line):
    (*columns, metadata) = line.strip().split('\t')
    (diff, timestamp) = metadata.split(' at ')
    operation = 'deleted' if diff.endswith('-1') else 'inserted'
    return (columns, operation, timestamp)

def main(table):
    for line in sys.stdin:
        (columns, operation, timestamp) = parse(line)
        payload = {'columns': columns, 'operation': operation, 'timestamp': timestamp}
        requests.post('http://localhost:8875/api/v1/{}'.format(table), json=payload)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument('table', help='Name of table to tail')
    args = parser.parse_args()
    main(args.table)
