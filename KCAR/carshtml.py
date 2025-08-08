import requests

cookies = {
    "_fwb": "24EntouEJn4xb6XMdPlqJW.1746917652505",
    "_kmpid": "km|www.kcar.com|1746917652508|35857808-237b-4fd5-8ee9-a220a428bb52",
    "_kmpid": "km|kcar.com|1746917652508|35857808-237b-4fd5-8ee9-a220a428bb52",
    "grb_ck@cbd6aecb": "9fd36013-fcd1-07ef-8992-fd71ddbcd830",
    "grb_ui@cbd6aecb": "7d5dd839-341f-0773-490d-91fea51469ef",
    "dmcself_fp": "babb221a5f384a6b128f7140fcc5368a",
    "_spfp": "sp.1.babb221a5f384a6b128f7140fcc5368a.1746917654",
    "_spfp_v2_2": "sp.2.2.1746917654.98575",
    "_ga_17DVLNK818": "deleted",
    "_ba_exist": "true",
    "_wp_uid": "1-9163bd69160f3f07cf0f0727bc852157-s1752559525.971541|mac_osx|chrome-1sbcs5v",
    "amplitude_id_86cd6422ba1c1dd78d122ad0b1158d6akcar.com": "eyJkZXZpY2VJZCI6IjIyNTI0MmI3LTAzOTItNDIzZS1hMjdmLTMwYzYwNmNlNDhiMFIiLCJ1c2VySWQiOm51bGwsIm9wdE91dCI6ZmFsc2UsInNlc3Npb25JZCI6MTc1NDQ3NjQzNDcyOCwibGFzdEV2ZW50VGltZSI6MTc1NDQ3NjQzNDcyOSwiZXZlbnRJZCI6MjEsImlkZW50aWZ5SWQiOjIyLCJzZXF1ZW5jZU51bWJlciI6NDN9",
    "_gid": "GA1.2.730044865.1754476435",
    "AMP_MKTG_86cd6422ba": "JTdCJTdE",
    "vuex": "%7B%22session%22%3A%7B%22member%22%3A%7B%7D%2C%22token%22%3Atrue%7D%2C%22sc%22%3A%7B%22homeSvc%22%3A%7B%22formData%22%3A%7B%7D%7D%7D%2C%22guest%22%3A%7B%22guest%22%3A%7B%7D%7D%2C%22chatbot%22%3A%7B%22chatbot%22%3A%7B%7D%7D%7D",
    "ab.storage.deviceId.79570721-e48c-4ca4-b9d6-e036e9bfeff8": "g%3Aa5843a86-041a-2cb8-3aa8-0d367c487685%7Ce%3Aundefined%7Cc%3A1754551590672%7Cl%3A1754626559001",
    "_ba_rand": "26",
    "_ba_ssid": "xhvzgAKm",
    "_ba_page_ct": "2025-08-08T04%3A16%3A04.356Z",
    "_ba_initial_refer": "",
    "_gcl_au": "1.1.566019518.1746917652",
    "grb_id_permission@cbd6aecb": "fail",
    "grb_ip_permission@cbd6aecb": "fail",
    "_ba_last_2nd_url": "https%3A%2F%2Fwww.kcar.com%2F",
    "_ba_page_seq": "3",
    "_ba_parent_seq": "3",
    "_ba_last_url": "https%3A%2F%2Fwww.kcar.com%2Fbc%2Fsearch%3FsearchCond%3D%257B%2522wr_eq_mnuftr_cd%2522%253A%2522001%2522%257D",
    "_ga_N2QC9KJL32": "GS2.1.s1754626559$o10$g1$t1754628302$j59$l0$h0",
    "_ga": "GA1.1.1284423820.1746917652",
    "_ga_12BKR6ZT1H": "GS2.2.s1754626564$o9$g1$t1754628305$j60$l0$h0",
    "ab.storage.sessionId.79570721-e48c-4ca4-b9d6-e036e9bfeff8": "g%3Ab6f4efde-4c3c-7838-063a-59f90eb14489%7Ce%3A1754630112329%7Cc%3A1754626559001%7Cl%3A1754628312329",
    "AMP_86cd6422ba": "JTdCJTIyZGV2aWNlSWQlMjIlM0ElMjJhNTg0M2E4Ni0wNDFhLTJjYjgtM2FhOC0wZDM2N2M0ODc2ODUlMjIlMkMlMjJzZXNzaW9uSWQlMjIlM0ExNzU0NjI2NTg4NDcwJTJDJTIyb3B0T3V0JTIyJTNBZmFsc2UlMkMlMjJsYXN0RXZlbnRUaW1lJTIyJTNBMTc1NDYyODMxMjM2OSUyQyUyMmxhc3RFdmVudElkJTIyJTNBMTUlMkMlMjJwYWdlQ291bnRlciUyMiUzQTAlN0Q=",
    "_ba_reload_count": "4",
    "_ba_click": "true",
    "__rtbh.uid": "%7B%22eventType%22%3A%22uid%22%2C%22id%22%3A%22undefined%22%2C%22expiryDate%22%3A%222026-08-08T04%3A45%3A21.575Z%22%7D",
    "__rtbh.lid": "%7B%22eventType%22%3A%22lid%22%2C%22id%22%3A%22ZY09ozr2u3zUDpedurcM%22%2C%22expiryDate%22%3A%222026-08-08T04%3A45%3A21.575Z%22%7D",
    "wcs_bt": "s_2486949985b2:1754628321",
    "cto_bundle": "iR8MjV9oakFOSzlGOUhZYzZjVCUyRmMlMkIzenI5aWtuRURGNFl1aEV6JTJCajZSaXY0RXRsVmx4JTJCcGdjJTJGMzBoUTRINmhCa2p3aFVRMWx0Nmdnb1JnVFFIVk5iUTNCc3U4VmVxV1hDeE1kZG9pdnREQnQwZG5SSzdwWlJvUFpuQmhNMGhNZFl1SGc1NWJ3bThyYXpTQmdndiUyQmo1SGlPUWZQbm5xWENjUEJQb3VCMnNNakNobmtnUk80ak5sUFc4c0FER2ZBYXp1aENrOVBVdDhDa2ZqcHVHbXpybHhwNUxRWnJYcllPOGdnbW1vaDFpaUhtJTJGVHBXcFVRRXJqNWMxWU1PdmRMQllMbFg",
    "_ga_17DVLNK818": "GS2.1.s1754626564$o10$g1$t1754628362$j30$l0$h0",
    "WMONID": "jC2xuEa6QTx",
}

headers = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "en,ru;q=0.9,en-CA;q=0.8,la;q=0.7,fr;q=0.6,ko;q=0.5",
    "Cache-Control": "max-age=0",
    "Connection": "keep-alive",
    "If-None-Match": '"1b9813-c3IYRa3ZCN2YIc/uIOgw/9qNkLw"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
    "sec-ch-ua": '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    # 'Cookie': '_fwb=24EntouEJn4xb6XMdPlqJW.1746917652505; _kmpid=km|www.kcar.com|1746917652508|35857808-237b-4fd5-8ee9-a220a428bb52; _kmpid=km|kcar.com|1746917652508|35857808-237b-4fd5-8ee9-a220a428bb52; grb_ck@cbd6aecb=9fd36013-fcd1-07ef-8992-fd71ddbcd830; grb_ui@cbd6aecb=7d5dd839-341f-0773-490d-91fea51469ef; dmcself_fp=babb221a5f384a6b128f7140fcc5368a; _spfp=sp.1.babb221a5f384a6b128f7140fcc5368a.1746917654; _spfp_v2_2=sp.2.2.1746917654.98575; _ga_17DVLNK818=deleted; _ba_exist=true; _wp_uid=1-9163bd69160f3f07cf0f0727bc852157-s1752559525.971541|mac_osx|chrome-1sbcs5v; amplitude_id_86cd6422ba1c1dd78d122ad0b1158d6akcar.com=eyJkZXZpY2VJZCI6IjIyNTI0MmI3LTAzOTItNDIzZS1hMjdmLTMwYzYwNmNlNDhiMFIiLCJ1c2VySWQiOm51bGwsIm9wdE91dCI6ZmFsc2UsInNlc3Npb25JZCI6MTc1NDQ3NjQzNDcyOCwibGFzdEV2ZW50VGltZSI6MTc1NDQ3NjQzNDcyOSwiZXZlbnRJZCI6MjEsImlkZW50aWZ5SWQiOjIyLCJzZXF1ZW5jZU51bWJlciI6NDN9; _gid=GA1.2.730044865.1754476435; AMP_MKTG_86cd6422ba=JTdCJTdE; vuex=%7B%22session%22%3A%7B%22member%22%3A%7B%7D%2C%22token%22%3Atrue%7D%2C%22sc%22%3A%7B%22homeSvc%22%3A%7B%22formData%22%3A%7B%7D%7D%7D%2C%22guest%22%3A%7B%22guest%22%3A%7B%7D%7D%2C%22chatbot%22%3A%7B%22chatbot%22%3A%7B%7D%7D%7D; ab.storage.deviceId.79570721-e48c-4ca4-b9d6-e036e9bfeff8=g%3Aa5843a86-041a-2cb8-3aa8-0d367c487685%7Ce%3Aundefined%7Cc%3A1754551590672%7Cl%3A1754626559001; _ba_rand=26; _ba_ssid=xhvzgAKm; _ba_page_ct=2025-08-08T04%3A16%3A04.356Z; _ba_initial_refer=; _gcl_au=1.1.566019518.1746917652; grb_id_permission@cbd6aecb=fail; grb_ip_permission@cbd6aecb=fail; _ba_last_2nd_url=https%3A%2F%2Fwww.kcar.com%2F; _ba_page_seq=3; _ba_parent_seq=3; _ba_last_url=https%3A%2F%2Fwww.kcar.com%2Fbc%2Fsearch%3FsearchCond%3D%257B%2522wr_eq_mnuftr_cd%2522%253A%2522001%2522%257D; _ga_N2QC9KJL32=GS2.1.s1754626559$o10$g1$t1754628302$j59$l0$h0; _ga=GA1.1.1284423820.1746917652; _ga_12BKR6ZT1H=GS2.2.s1754626564$o9$g1$t1754628305$j60$l0$h0; ab.storage.sessionId.79570721-e48c-4ca4-b9d6-e036e9bfeff8=g%3Ab6f4efde-4c3c-7838-063a-59f90eb14489%7Ce%3A1754630112329%7Cc%3A1754626559001%7Cl%3A1754628312329; AMP_86cd6422ba=JTdCJTIyZGV2aWNlSWQlMjIlM0ElMjJhNTg0M2E4Ni0wNDFhLTJjYjgtM2FhOC0wZDM2N2M0ODc2ODUlMjIlMkMlMjJzZXNzaW9uSWQlMjIlM0ExNzU0NjI2NTg4NDcwJTJDJTIyb3B0T3V0JTIyJTNBZmFsc2UlMkMlMjJsYXN0RXZlbnRUaW1lJTIyJTNBMTc1NDYyODMxMjM2OSUyQyUyMmxhc3RFdmVudElkJTIyJTNBMTUlMkMlMjJwYWdlQ291bnRlciUyMiUzQTAlN0Q=; _ba_reload_count=4; _ba_click=true; __rtbh.uid=%7B%22eventType%22%3A%22uid%22%2C%22id%22%3A%22undefined%22%2C%22expiryDate%22%3A%222026-08-08T04%3A45%3A21.575Z%22%7D; __rtbh.lid=%7B%22eventType%22%3A%22lid%22%2C%22id%22%3A%22ZY09ozr2u3zUDpedurcM%22%2C%22expiryDate%22%3A%222026-08-08T04%3A45%3A21.575Z%22%7D; wcs_bt=s_2486949985b2:1754628321; cto_bundle=iR8MjV9oakFOSzlGOUhZYzZjVCUyRmMlMkIzenI5aWtuRURGNFl1aEV6JTJCajZSaXY0RXRsVmx4JTJCcGdjJTJGMzBoUTRINmhCa2p3aFVRMWx0Nmdnb1JnVFFIVk5iUTNCc3U4VmVxV1hDeE1kZG9pdnREQnQwZG5SSzdwWlJvUFpuQmhNMGhNZFl1SGc1NWJ3bThyYXpTQmdndiUyQmo1SGlPUWZQbm5xWENjUEJQb3VCMnNNakNobmtnUk80ak5sUFc4c0FER2ZBYXp1aENrOVBVdDhDa2ZqcHVHbXpybHhwNUxRWnJYcllPOGdnbW1vaDFpaUhtJTJGVHBXcFVRRXJqNWMxWU1PdmRMQllMbFg; _ga_17DVLNK818=GS2.1.s1754626564$o10$g1$t1754628362$j30$l0$h0; WMONID=jC2xuEa6QTx',
}

params = {
    "searchCond": '{"wr_eq_mnuftr_cd":"001"}',
}

response = requests.get(
    "https://www.kcar.com/bc/search", params=params, cookies=cookies, headers=headers
)
