#!/usr/bin/python3
# -*- coding: utf-8 -*-

import json
import urllib.request, urllib.error, urllib.parse
from argparse import ArgumentParser
import ipaddress
import base64
import re
import os
import shutil
import tempfile
import zipfile

current_dir = os.path.dirname(__file__)

def parse_args():
    parser = ArgumentParser()
    parser.add_argument('-f', '--file', dest='output', 
                        help='输出的PAC文件名', default='pac',
                        metavar='PAC')
    parser.add_argument('-p', '--proxy', dest='proxy',
                        help='代理服务器, 如, "PROXY 127.0.0.1:3128;"',
                        default='PROXY 127.0.0.1:1080',
                        metavar='PROXY')
    parser.add_argument('--sub-proxy-domains', dest='proxy_rule',
                        default=os.path.join(current_dir, 'proxy-domain.txt'),
                        help='代理的域名文件，每行一个，只能是二级域名')
    parser.add_argument('--sub-direct-domains', dest='direct_rule',
                        default=os.path.join(current_dir, 'direct-domain.txt'),
                        help='直连的域名文件，每行一个，只能是二级域名')
    parser.add_argument('--direct-cidr', dest='ip_file',
                        default=os.path.join(current_dir, 'direct-cidr.txt'),
                        help='直连IP地址段文件')
    parser.add_argument('--geoip2-authkey', dest='geoip2_authkey',
                        help='geoip2 认证 key')
    return parser.parse_args()

current_dir = os.path.dirname(__file__)
temp_dir = tempfile.mkdtemp()
print(f"创建临时目录 {temp_dir}")


def read_or_create_file(file_path):
    result = ''
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        return content
    else:
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write('')
        return result

def remove2dot(line):
    dots = [i for i, char in enumerate(line) if char == '.']
    if len(dots) > 1:
        return line[dots[-2] + 1:].strip()
    else:
        return line.strip()

def generate_cnip_cidrs(filepath):
    """ 从文件中读取CIDR地址 """
    args = parse_args()
    with open(filepath, 'r') as file:
        return file.read().splitlines()

def generate_pac_fast(proxy, domains, direct_domains, cidrs):
    # render the pac file
    with open('./pac-template', 'r') as f:
        proxy_content = f.read()

    proxy_content = proxy_content.replace('__PROXY__', json.dumps(str(proxy)))

    print(f'proxy domain length: {len(domains)}')
    proxy_content = proxy_content.replace(
        '__PROXY_DOMAINS__',
        json.dumps(domains, sort_keys=True, separators=(',', ':'))
    )

    print(f'direct domain length: {len(direct_domains)}')
    proxy_content = proxy_content.replace(
        '__DIRECT_DOMAINS__',
        json.dumps(direct_domains, sort_keys=True, separators=(',', ':'))
    )

    print(f'direct cidr length: {len(cidrs)}')
    proxy_content = proxy_content.replace(
        '__DIRECT_CIDRS__', 
        json.dumps(cidrs, sort_keys=True, separators=(',', ':'))
    )

    return proxy_content

def gfwlist():
    gfwurl = 'https://pagure.io/gfwlist/raw/master/f/gfwlist.txt'
    content = urllib.request.urlopen(gfwurl, timeout=10).read().decode('utf-8')
    content = base64.b64decode(content).decode('utf-8')
    result = {}
    for line in content.splitlines():
        line = line.strip()
        if not line.startswith('||'):
            continue
        line=line.removeprefix('||')
        result[remove2dot(line)]=True
    return result

def domainListFiles():
    url = 'https://github.com/v2fly/domain-list-community/archive/refs/heads/master.zip'

    zip_path = os.path.join(temp_dir, "master.zip")
    urllib.request.urlretrieve(url, zip_path)
    
    with zipfile.ZipFile(zip_path, 'r') as f:
        f.extractall(temp_dir)

    extracted_dir = os.path.join(temp_dir, 'domain-list-community-master')
    
    os.chdir(extracted_dir)
    noncn = 'geolocation-!cn'
    cn = 'geolocation-cn'
    print(f'cmd: domain-list-community -exportlists {noncn},{cn}')
    result = os.system(f'domain-list-community -exportlists {noncn},{cn} > /dev/null 2>&1')
    if result!=0:
        raise("domain list failed")
    def parse(line):
        if line.find('@cn')>-1 or line.find('@ad')>-1:
            return ''
        line = line.split(':@')[0]
        # 若一级域名超出5位，不跟踪
        slice_line = line.split('.')
        if len(slice_line[len(slice_line)-1])>5:
            return ''
        if line.startswith('domain'): 
            return remove2dot(line.removeprefix('domain:'))
        if line.startswith('full'): 
            return remove2dot(line.removeprefix('full:'))
        return ''
    cndict = {}
    ncndict = {}
    with open(os.path.join(extracted_dir,noncn+'.txt'), 'r') as f:
        for line in f.readlines():
            line = parse(line.strip())
            if line:
                ncndict[line]=True
    with open(os.path.join(extracted_dir,cn+'.txt'), 'r') as f:
        for line in f.readlines():
            line = parse(line.strip())
            if line:
                cndict[line]=True
    return (cndict, ncndict)

def geoip2Files(key):
    if key is None or len(key)==0:
        print('没有提供 geoip2 认证密钥')
        return {}
    url = f'https://download.maxmind.com/app/geoip_download?edition_id=GeoLite2-Country-CSV&license_key={key}&suffix=zip'

    zip_path = os.path.join(temp_dir, "geoip2.zip")
    urllib.request.urlretrieve(url, zip_path)
    
    with zipfile.ZipFile(zip_path, 'r') as f:
        f.extractall(temp_dir)

    
    result = os.system(f'mv {temp_dir}/GeoLite2* {temp_dir}/geolite2')
    if result != 0:
        raise("move geolite2 dir failed")

    os.chdir(temp_dir)
    with open('config.json','w', encoding='utf-8') as f:
        f.write('''{
  "input": [
    {
      "type": "maxmindGeoLite2CountryCSV",
      "action": "add",
      "args": {
        "ipv4": "./geolite2/GeoLite2-Country-Blocks-IPv4.csv"
      }
    },
    {
      "type": "private",
      "action": "add"
    }
  ],
  "output": [
    {
      "type": "text",
      "action": "output",
      "args": {
        "outputDir": "./output",
        "oneFilePerList": true,
        "wantedList": ["cn", "private"]
      }
    },
    {
      "type": "text",
      "action": "output"
    }
  ]
}
''')
    result = os.system(f'geoip > /dev/null 2>&1')
    if result!=0:
        raise("domain list failed")
    cn = os.path.join(temp_dir,'output/cn.txt')
    private = os.path.join(temp_dir,'output/private.txt')

    cidr_dict = {}

    def read_to_dict(map, file_path):
        with open(file_path,'r') as f:
            for line in f.readlines():
                map[line.strip()]=True
    read_to_dict(cidr_dict, cn)
    read_to_dict(cidr_dict, private)
    return cidr_dict

def main():
    args = parse_args()
    proxy_rule = []
    direct_rule = []
    cidr_rule = []
    
    # direct cidr
    cidr_content = read_or_create_file(args.ip_file)
    cidr_dict = geoip2Files(args.geoip2_authkey)
    for line in cidr_content.splitlines():
        l = line.strip()
        if l:
            cidr_dict[l]=True
    cidr_rule = sorted(cidr_dict.keys())

    # proxy domain
    os.chdir(current_dir)
    proxy_content = read_or_create_file(args.proxy_rule)
    cn_dict, ncn_dict = domainListFiles()
    for c in proxy_content.splitlines():
        l = c.strip()
        if l:
            ncn_dict[l]=True
    # for key, values in gfwlist().items():
    #     ncn_dict[key]=True
    proxy_rule = sorted(ncn_dict.keys())

    # direct domain
    os.chdir(current_dir)
    direct_content = read_or_create_file(args.direct_rule)
    for line in direct_content.splitlines():
        l = line.strip()
        if l:
            cn_dict[l]=True
    direct_rule = sorted(cn_dict.keys())

    os.chdir(current_dir)
    pac_content = generate_pac_fast(args.proxy, proxy_rule, direct_rule, cidr_rule)

    with open(args.output, 'w') as f:
        f.write(pac_content)

    # 清理临时目录
    shutil.rmtree(temp_dir)

if __name__ == '__main__':
    main()