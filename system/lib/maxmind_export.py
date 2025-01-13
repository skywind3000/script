#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#======================================================================
#
# test_export.py - 
#
# Created by skywind on 2025/01/13
# Last Modified: 2025/01/13 17:12:30
#
#======================================================================
import sys


#----------------------------------------------------------------------
# reader
#----------------------------------------------------------------------
def mmdb_reader(mmdb_file):
    import maxminddb
    with maxminddb.open_database(mmdb_file) as reader:
        for network, record in reader:
            data = {
                'continent_code': record.get('continent', {}).get('code'),
                'continent_name': record.get('continent', {}).get('names', {}).get('en'),
                'country_iso_code': record.get('country', {}).get('iso_code'),
                'country_name': record.get('country', {}).get('names', {}).get('en'),
                'traits_is_anonymous_proxy': record.get('traits', {}).get('is_anonymous_proxy')
            }
            yield [str(network), data]
    return 0


#----------------------------------------------------------------------
# extract
#----------------------------------------------------------------------
def mmdb_extract(mmdb_file, output = None):
    import csv

    if output is None:
        fp = sys.stdout
    elif isinstance(output, str):
        fp = open(output, mode='w', newline='', encoding='utf-8')
    else:
        fp = output

    fieldnames = ['network', 'continent_code', 'continent_name', 
                  'country_iso_code', 'country_name', 
                  'traits_is_anonymous_proxy']

    writer = csv.DictWriter(fp, fieldnames = fieldnames)

    # Write the header
    writer.writeheader()

    # Iterate through all records in the MMDB file
    for network, record in mmdb_reader(mmdb_file):
        # Prepare the row data
        row = record
        row['network'] = network
        # Write the row to the CSV file
        # print(row)
        writer.writerow(row)

    return 0


#----------------------------------------------------------------------
# main()
#----------------------------------------------------------------------
def main(argv = None):
    argv = [n for n in (argv and argv or sys.argv)]
    if len(argv) < 2:
        print('usage: %s mmdb_file [csv_file]' % argv[0])
        return 1
    mmdb_file = argv[1]
    if len(argv) > 2:
        output = argv[2]
    else:
        output = None
    mmdb_extract(mmdb_file, output)
    return 0


#----------------------------------------------------------------------
# testing suit
#----------------------------------------------------------------------
if __name__ == '__main__':
    def test1():
        mmdb_extract('maxmind/GeoIP2-Country.mmdb', 'output.csv')
        return 0
    # test1()
    main()


