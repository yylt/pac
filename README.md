## pac

参考项目 [gfw-pac](https://github.com/zhiyi7/gfw-pac) 实现.

## 特点

- [x] 使用 trieTree，支持 domain 匹配，但只到二级域名

- [x] 从 [gfwlist](https://pagure.io/gfwlist), [domain-list-community](https://github.com/v2fly/domain-list-community) 获取代理和直连域名

- [x] 从 [geolite2](https://www.maxmind.com/en/home) 下载 CIDR 信息，获取 cn 区域

- [ ] 自动发布到 github release

## 使用

- 环境需预装工具
    - domain-list-community: go install github.com/v2fly/domain-list-community@latest
    - geoip:go install github.com/v2fly/geoip@latest

- 生成 

```
python3 pac-gen.py \
    --geoip2-authkey xx \
    --sub-proxy-domains ./proxy-domain.txt \ 
    --sub-direct-domains ./direct-domain.txt \
    --direct-cidr ./direct-cidr-phone.txt \
    -p "PROXY 127.0.0.1:1080; DIRECT" \
    -f ./pac
```