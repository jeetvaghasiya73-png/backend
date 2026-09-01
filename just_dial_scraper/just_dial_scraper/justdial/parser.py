from datetime import datetime
import json 
import socket
import subprocess
import time
from curl_cffi import requests
from playwright.sync_api import sync_playwright
import random



def get_location(city,search):
    cookies = {
        'ppc': '',
        '_ctok': '417318fde1d131786899332326833tw4oF3jpCqtok5y4E5D6Fng4h5x8E3xEE',
        'web_visit': '2026-08-16T16:55:32.326Z',
        'jd_www_nxt': '1',
        '_gcl_au': '1.1.1359176709.1786899334',
        '_ga': 'GA1.1.1342468170.1786899334',
        '__gsas': 'ID=f657c6498fec3f1e:T=1786899364:RT=1786899364:S=ALNI_MbCnEfauKPEq0XoXcqa9o2l6DbM6Q',
        'MP_city': 'Bardoli',
        'MP_area': 'Bardoli Suart Road Sardar Baug',
        'MP_pincode': '394601',
        'MP_lat': '21.115989685058594',
        'MP_long': '73.10640716552734',
        'scity': 'Bardoli',
        'inweb_city': 'Bardoli',
        'sarea': 'Bardoli Suart Road Sardar Baug',
        'pincode': '394601',
        'alat': '21.115989685058594',
        'alon': '73.10640716552734',
        '__gads': 'ID=6a7c2c7ff9ffd377:T=1786899338:RT=1786903146:S=ALNI_MY9h6Uf9DjEjpDgvO-VFX0dmnWAzQ',
        '__gpi': 'UID=000014e4f34ad7c2:T=1786899338:RT=1786903146:S=ALNI_MbN1XAGJbeNdCVOEH-szm37dZneXw',
        '__eoi': 'ID=fa6be4f5da07f1a2:T=1786899338:RT=1786903146:S=AA-AfjawidQs0YkVR6COGukoIkzD',
        'rfr': 'gen',
        'ppc': '',
        'Continent': 'AS',
        'Ak_City': 'AHMEDABAD',
        'Cntry': 'IN',
        'bm_so': '51F58ED4DDBD1510712BDAC6444E843C6D02A1330D3354024EF56CCD955ECC9B~YAAQrIosMU7e2vifAQAAVO2CEAhHViKY+9Bvi6CHvtFjOBNSDePQMir0VZAMR4ADjoz/JNyfaCTnCryH36vpqwZLN6FC0VGfxsw/bIgp28uzEv7r595dTau7zrbxIEC+k2c14Y72l7S+wBDtvvR+Cesn0fp8H9OzucO97No91hSz+vEAkulSiZ/amMkyekLR49WcRASMX79rAiJ1Ldp2KOOusvP8y22CR5a74gAEwNEZ2+15FFz1aq+9TASqJ3DnoPyMp93PSyQFfcpr63MEBZSi4Q1reOMdOydPW0o+8xG7TXvgtCcnvR5jpvJYqbSuq+lUTMFc//oqkGORpDAdk4HHYpH/6YjqjZI4y0jekq7UnR3cqJnoxV8yHu0pr9z5ukHfcUYBdKY5EfIOzATMY1yRz2jO84/JLHrWUz0qj98UJwvTYgau6X4/g9ubBBfaouhnV6OSdVR/WFxae/nlq/b84Qc=',
        'bm_sz': '9701A4DB7E60D6DFE8C4BF5D7A369446~YAAQrIosMU/e2vifAQAAVO2CEADJE1vTkIqLpGp+Kfs0zF31m+Yu38xZz9QH2TXPaIx6W5rsjUd2iJ/tpGvHE34xISNDw+hUd4U+E1Ksi6LWppk5CANG8tWlhStjQ0xIn8CbLmwN5eTIJWd3WwdSt/OzN/djZ81UuUEqGWNsYu8Y9DEpfjKEhw+Ne2oQUumTloJkTpGMv6+8WViwe/mas+vFD3vbp3wisIIBXt1wdBNEo5hHOc6FfqU2wZuX6f6GczgIfw17XrSQOEXc3uI7+a2ZdF2RP0VfJqPkvGJL53EYFjiuxaCdKEB3T1OuWxulQ2HaiuJdK5TYqWS73aR3/ma8IuKFDKXmvWxJG3b6J+9e+rR7QliEoQ5xHvipSOSdbNtbmkn5LUG3WEG/RCdT~4469553~3616821',
        '_abck': '7C75092B22276F364CE39354B0850A74~0~YAAQpYosMbu/Jw6gAQAA9u2CEBC6iuXP3I9VnSzOVuL2+0Cnobi38vY+SnjXv2+MWnSdpC6PvGzjp7ik4bc9MgE3PSbTyMrnKTePqlw3tC7oVG86tC53tEGOYb8hG/8AAZjzFYQNMCptQqpQ6xqrnHzrMNrctJaNJtDPYWKEN46L3eyMS3mQbe8lHPOTjGBMfv0hfWDe9t6frKtTasaE6aP+M2cM4N13m0TgYxFCBz4anOwqLetczZ2lXftRXwaUI0E/pYopjb6t4ZP3Rd3HitpIxUpjAHarjV/LVa4ZxJYTGDeamMfaty86LjNCW7WnO3P/ygxsgH1EbpDw9wIyr9mHQnHFtfFgoyx+ej/wfZqRNZEFKTXu0iDoPNJer+s0bQ6BgojUUIiCXF8Dk09/CuCn38w/tb6EVKuRJurbz42QhfDD3nl6jBmxt5/L0IyuBnpKMrJ1cQwnzOJrWqs4RYbkwH8mLtwGQI8DwD2qRUBs30OqiHt5TOfmLH6UeLwEV7kH0XY1zCk/+Byl1jGFHzlG451ggzwivRjCX3BPKiuKsP6Gs9vFr8kP9MQsbJLGv/HQAIzbyoMf3xGbKhdpMwKrcGT4greto0FgUvkf0LgkJQt/Oa2NzzEkBskBAp/rhNhVsNTvsBoen620OeDcaNhfosRt4cChazoEr2AdTdpPGgnPX14KufGM1kKunllA8hSzYA==~-1~-1~-1~AAQAAAAG%2f%2f%2f%2f%2f6YLDhVa6moTCwUjZIPFn5MpRTpnsxXoBOI8ufyxMHYXwTLaIS+vX7P8iBL3++opYFK2fVA2nY+J5zdT+RjW3jDxQbkys5ukqEky~-1',
        '_wbssid': 'webBC56810E6FC2098B56D56A7C5280E032',
        'ak_bmsc': 'EFCAA62AE66C69047827B1B7988EB9C8~000000000000000000000000000000~YAAQpYosMUjAJw6gAQAApPGCEABDehhMh+62Wf3ZiGK3JdheVLeCvzchLcjEFGbBshZOFpw4np/rvSLGYGPInTSh/ywDnRp42+u06GFkfBwcP+NrEqSwScMgA+ueGqzt4HvhWp0+dl9NvPun6H0AGELQ8pEfx12+j4Lx9sai9graY8ZYk8p4ofAMpfiU//U+bAW04BEE05XFeykUh/T5gqV0AhusIAjZdJEI4lRrLsnZ670e4g44C3Iy1Itu8G3YXCvQ2WhbG1zvyydu+C7Tz2ODNBeogwLW6BWP4GpZIqvKH7fxRfTFiZMKgojg172tzMufvQoq4aYm7B30zQy9qijBYUjUMj+MTxhLYp11K886V0tXtbU5B6wPfJ9089ZVawx44vtInC9ll/bft//vAdh+t8SU8Pbgl7rZjgcB+xzEvsExuYBcQfJf+XBVvRlCfIuie4C5aw==',
        '_ga_PGCZHZY9JF': 'GS2.1.s1786983412$o3$g0$t1786983412$j60$l0$h0',
        'FCCDCF': '%5Bnull%2Cnull%2Cnull%2Cnull%2Cnull%2Cnull%2C%5B%5B32%2C%22%5B%5C%22443db8f8-be0f-4b92-98bd-73ebba0ee2bd%5C%22%2C%5B1786899334%2C505000000%5D%5D%22%5D%5D%5D',
        '_uetsid': '4c3266d0999311f1930d052c153bdd24',
        '_uetvid': '4c328430999311f1916055e7b33e24ba',
        'bm_lso': '51F58ED4DDBD1510712BDAC6444E843C6D02A1330D3354024EF56CCD955ECC9B~YAAQrIosMU7e2vifAQAAVO2CEAhHViKY+9Bvi6CHvtFjOBNSDePQMir0VZAMR4ADjoz/JNyfaCTnCryH36vpqwZLN6FC0VGfxsw/bIgp28uzEv7r595dTau7zrbxIEC+k2c14Y72l7S+wBDtvvR+Cesn0fp8H9OzucO97No91hSz+vEAkulSiZ/amMkyekLR49WcRASMX79rAiJ1Ldp2KOOusvP8y22CR5a74gAEwNEZ2+15FFz1aq+9TASqJ3DnoPyMp93PSyQFfcpr63MEBZSi4Q1reOMdOydPW0o+8xG7TXvgtCcnvR5jpvJYqbSuq+lUTMFc//oqkGORpDAdk4HHYpH/6YjqjZI4y0jekq7UnR3cqJnoxV8yHu0pr9z5ukHfcUYBdKY5EfIOzATMY1yRz2jO84/JLHrWUz0qj98UJwvTYgau6X4/g9ubBBfaouhnV6OSdVR/WFxae/nlq/b84Qc=~1786983413245',
        'bm_s': 'YAAQpYosMcPAJw6gAQAAhviCEAUT+CwlfiPMIDX1H2r5PphFrGeZlPO/zErQ+DxdgI1X03QdScAPAfKVmwl/A0pVpRDafONC7aeCVtMyZZsUPba8hK0Pkye4s+noxUZ40SZ/eLPaoGENuv/6GjUHzkK8dB3UgOQLu+8WoPGKe2PEpb0+Ai/1ebkwWgu/j7gIBhit+O1tkKAD8wx9+6OJXEmTQ2hqXt5H/HfQFpLXTnV5rJBe3zqUvZmoQVIQmeGnT2jMuxGas+pHPaU2uAVaO77+ytCNox5dK7TEAZQIzvbCZQYHQIzT104+COcK3ONqHjXug+FVxmc0mhRWLA1jNhnesg6vcbRv9RX8junMffJGn3RkOztnPYV6UVlX55SqKwq6pkYoVB8ZQrgVyxpOlZU1+gmYnFNOHpP2Roiw3XW0JjLo6sNzEqkJiBp3nBbKTAeFlSZAHxAZKqAWM5LqU+p3eC79sc8DZjBS6pb6CMayIXGqlF2631528RVaVXbSPrTuJT1CnpD1YplnfzxsIDgvU8OuDePz7YPZHZIdOdqcI1nC1jfAxSZ/34haOimZFce0to0RlXZQtZp/4+ifumYp3T3xLCVEWwaQcgb5IzJi88sGF8HG/nH4BdU9DGUIbDDGMvQlSvFX05aVF329Q6NvxOv/kJw/nvRhhU7ExMZsgk1hcIIa4FPJgNcwIb9M2yI/sAWn48Lq0Dx9aLS9xyUNbg2AatSIsqAvg9gqiD9t4fGQ3BZ7Gq2Hkio2Bllxa7mbGhkc6hpQPljd5TewHAknAD28KqT5vu+GcgAvsMvNhmVOP8mj/kemriBl6lNUEYKMs7Z6JkyDQsYe0/jxjteBQoCUHS/SNTJBXSzs3S0C8n6s4WKFS8uKLJm4cDtUeP/eNTwz2juINO+I6efJ8Uj8E/xMMtPkysZQN1Zf8FbQOEurje8zxS4F5RNVD4unJMaVJf1RR/RPRFFmd7w6pYLw6dYEye7RZbqymTZcC0uN9Z4/GuSKXHA577QdmtwssafCuOEhXHWsU6bf0Jidk7XcumYfhvF6uxyRn8H5gpMzXXQVvCxsw2uWkF811cc=',
        'FCNEC': '%5B%5B%22AKsRol-IFreiGARzkkwTYImFM33CHqoQIBs9OM34Ui9_Cr7IecMrPoXChCvAfw-23pAgocyofFgxD_c3RbsdT6nHMSBc42K7rds5JmSwmiIuHrxhdpWZrrx9l4lKVSChp_HJLopKcbo-c08P2MnjOS3l_XU4yB513A%3D%3D%22%5D%5D',
        '_ga_5PY4KYQRFS': 'GS2.1.s1786983413$o6$g0$t1786983418$j55$l0$h0',
        'bm_sv': '9A82F768515B6634BA7B61809DDEFB29~YAAQpYosMSPJJw6gAQAA6FCDEAAFhQReFWCAT5L7BcETQlpDTISbyAPiPKMo/3AQ6WbiVFmt5Fk0Oyta+fb9FYk+mswAKpiIK1qxEXDQgJx2xwmRZJ9DTtRm2F38jD4sbyxiYMyVsT21fz9Js0cBoP2sLPxDek9uWpcMZ5SYcbVlzkkDRiG51Ijalac05bBhhcknIDpzDictd3A7SBR0uz8SOMnCFEXewB+M1vIuXvJhvPTf+4tH9PC/uRKPRYqYI0rH~1',
        'RT': '"z=1&dm=justdial.com&si=a08c460d-21d2-41b9-a308-36edae6703ed&ss=msxfs8c8&sl=1&tt=1vr&rl=1&ld=1vr&nu=9y8m6cy&cl=mk2"',
    }

    headers = {
        'accept': 'application/json, text/plain, */*',
        'accept-language': 'en-US,en;q=0.9',
        'cache-control': 'no-cache',
        'content-type': 'application/json',
        'jdpk': '',
        'origin': 'https://www.justdial.com',
        'pragma': 'no-cache',
        'priority': 'u=1, i',
        'referer': 'https://www.justdial.com/',
        'requesttime': '2026-17-8%209%3A47%3A19%20PM',
        'sec-ch-ua': '"Not=A?Brand";v="99", "Google Chrome";v="151", "Chromium";v="151"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'securitytoken': '2a282a2e292f20212c2f2921',
        'sw8': '1-OWIyYmVhODEzNDM2NDkxYmIyMzU5Y2Y4OGFmNDUzYWM=-ZjBjN2YyNGEtOTJjZi00Yzk2LTgwYmQtMzcxODRkODI5NDE2-0-d3d3LWRlc2t0b3A6Ond3dy5qdXN0ZGlhbC5jb20=-di0wNzA4MjAyNg==-Lw==-d3d3Lmp1c3RkaWFsLmNvbQ==',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36',
        # 'cookie': 'ppc=; _ctok=417318fde1d131786899332326833tw4oF3jpCqtok5y4E5D6Fng4h5x8E3xEE; web_visit=2026-08-16T16:55:32.326Z; jd_www_nxt=1; _gcl_au=1.1.1359176709.1786899334; _ga=GA1.1.1342468170.1786899334; __gsas=ID=f657c6498fec3f1e:T=1786899364:RT=1786899364:S=ALNI_MbCnEfauKPEq0XoXcqa9o2l6DbM6Q; MP_city=Bardoli; MP_area=Bardoli Suart Road Sardar Baug; MP_pincode=394601; MP_lat=21.115989685058594; MP_long=73.10640716552734; scity=Bardoli; inweb_city=Bardoli; sarea=Bardoli Suart Road Sardar Baug; pincode=394601; alat=21.115989685058594; alon=73.10640716552734; __gads=ID=6a7c2c7ff9ffd377:T=1786899338:RT=1786903146:S=ALNI_MY9h6Uf9DjEjpDgvO-VFX0dmnWAzQ; __gpi=UID=000014e4f34ad7c2:T=1786899338:RT=1786903146:S=ALNI_MbN1XAGJbeNdCVOEH-szm37dZneXw; __eoi=ID=fa6be4f5da07f1a2:T=1786899338:RT=1786903146:S=AA-AfjawidQs0YkVR6COGukoIkzD; rfr=gen; ppc=; Continent=AS; Ak_City=AHMEDABAD; Cntry=IN; bm_so=51F58ED4DDBD1510712BDAC6444E843C6D02A1330D3354024EF56CCD955ECC9B~YAAQrIosMU7e2vifAQAAVO2CEAhHViKY+9Bvi6CHvtFjOBNSDePQMir0VZAMR4ADjoz/JNyfaCTnCryH36vpqwZLN6FC0VGfxsw/bIgp28uzEv7r595dTau7zrbxIEC+k2c14Y72l7S+wBDtvvR+Cesn0fp8H9OzucO97No91hSz+vEAkulSiZ/amMkyekLR49WcRASMX79rAiJ1Ldp2KOOusvP8y22CR5a74gAEwNEZ2+15FFz1aq+9TASqJ3DnoPyMp93PSyQFfcpr63MEBZSi4Q1reOMdOydPW0o+8xG7TXvgtCcnvR5jpvJYqbSuq+lUTMFc//oqkGORpDAdk4HHYpH/6YjqjZI4y0jekq7UnR3cqJnoxV8yHu0pr9z5ukHfcUYBdKY5EfIOzATMY1yRz2jO84/JLHrWUz0qj98UJwvTYgau6X4/g9ubBBfaouhnV6OSdVR/WFxae/nlq/b84Qc=; bm_sz=9701A4DB7E60D6DFE8C4BF5D7A369446~YAAQrIosMU/e2vifAQAAVO2CEADJE1vTkIqLpGp+Kfs0zF31m+Yu38xZz9QH2TXPaIx6W5rsjUd2iJ/tpGvHE34xISNDw+hUd4U+E1Ksi6LWppk5CANG8tWlhStjQ0xIn8CbLmwN5eTIJWd3WwdSt/OzN/djZ81UuUEqGWNsYu8Y9DEpfjKEhw+Ne2oQUumTloJkTpGMv6+8WViwe/mas+vFD3vbp3wisIIBXt1wdBNEo5hHOc6FfqU2wZuX6f6GczgIfw17XrSQOEXc3uI7+a2ZdF2RP0VfJqPkvGJL53EYFjiuxaCdKEB3T1OuWxulQ2HaiuJdK5TYqWS73aR3/ma8IuKFDKXmvWxJG3b6J+9e+rR7QliEoQ5xHvipSOSdbNtbmkn5LUG3WEG/RCdT~4469553~3616821; _abck=7C75092B22276F364CE39354B0850A74~0~YAAQpYosMbu/Jw6gAQAA9u2CEBC6iuXP3I9VnSzOVuL2+0Cnobi38vY+SnjXv2+MWnSdpC6PvGzjp7ik4bc9MgE3PSbTyMrnKTePqlw3tC7oVG86tC53tEGOYb8hG/8AAZjzFYQNMCptQqpQ6xqrnHzrMNrctJaNJtDPYWKEN46L3eyMS3mQbe8lHPOTjGBMfv0hfWDe9t6frKtTasaE6aP+M2cM4N13m0TgYxFCBz4anOwqLetczZ2lXftRXwaUI0E/pYopjb6t4ZP3Rd3HitpIxUpjAHarjV/LVa4ZxJYTGDeamMfaty86LjNCW7WnO3P/ygxsgH1EbpDw9wIyr9mHQnHFtfFgoyx+ej/wfZqRNZEFKTXu0iDoPNJer+s0bQ6BgojUUIiCXF8Dk09/CuCn38w/tb6EVKuRJurbz42QhfDD3nl6jBmxt5/L0IyuBnpKMrJ1cQwnzOJrWqs4RYbkwH8mLtwGQI8DwD2qRUBs30OqiHt5TOfmLH6UeLwEV7kH0XY1zCk/+Byl1jGFHzlG451ggzwivRjCX3BPKiuKsP6Gs9vFr8kP9MQsbJLGv/HQAIzbyoMf3xGbKhdpMwKrcGT4greto0FgUvkf0LgkJQt/Oa2NzzEkBskBAp/rhNhVsNTvsBoen620OeDcaNhfosRt4cChazoEr2AdTdpPGgnPX14KufGM1kKunllA8hSzYA==~-1~-1~-1~AAQAAAAG%2f%2f%2f%2f%2f6YLDhVa6moTCwUjZIPFn5MpRTpnsxXoBOI8ufyxMHYXwTLaIS+vX7P8iBL3++opYFK2fVA2nY+J5zdT+RjW3jDxQbkys5ukqEky~-1; _wbssid=webBC56810E6FC2098B56D56A7C5280E032; ak_bmsc=EFCAA62AE66C69047827B1B7988EB9C8~000000000000000000000000000000~YAAQpYosMUjAJw6gAQAApPGCEABDehhMh+62Wf3ZiGK3JdheVLeCvzchLcjEFGbBshZOFpw4np/rvSLGYGPInTSh/ywDnRp42+u06GFkfBwcP+NrEqSwScMgA+ueGqzt4HvhWp0+dl9NvPun6H0AGELQ8pEfx12+j4Lx9sai9graY8ZYk8p4ofAMpfiU//U+bAW04BEE05XFeykUh/T5gqV0AhusIAjZdJEI4lRrLsnZ670e4g44C3Iy1Itu8G3YXCvQ2WhbG1zvyydu+C7Tz2ODNBeogwLW6BWP4GpZIqvKH7fxRfTFiZMKgojg172tzMufvQoq4aYm7B30zQy9qijBYUjUMj+MTxhLYp11K886V0tXtbU5B6wPfJ9089ZVawx44vtInC9ll/bft//vAdh+t8SU8Pbgl7rZjgcB+xzEvsExuYBcQfJf+XBVvRlCfIuie4C5aw==; _ga_PGCZHZY9JF=GS2.1.s1786983412$o3$g0$t1786983412$j60$l0$h0; FCCDCF=%5Bnull%2Cnull%2Cnull%2Cnull%2Cnull%2Cnull%2C%5B%5B32%2C%22%5B%5C%22443db8f8-be0f-4b92-98bd-73ebba0ee2bd%5C%22%2C%5B1786899334%2C505000000%5D%5D%22%5D%5D%5D; _uetsid=4c3266d0999311f1930d052c153bdd24; _uetvid=4c328430999311f1916055e7b33e24ba; bm_lso=51F58ED4DDBD1510712BDAC6444E843C6D02A1330D3354024EF56CCD955ECC9B~YAAQrIosMU7e2vifAQAAVO2CEAhHViKY+9Bvi6CHvtFjOBNSDePQMir0VZAMR4ADjoz/JNyfaCTnCryH36vpqwZLN6FC0VGfxsw/bIgp28uzEv7r595dTau7zrbxIEC+k2c14Y72l7S+wBDtvvR+Cesn0fp8H9OzucO97No91hSz+vEAkulSiZ/amMkyekLR49WcRASMX79rAiJ1Ldp2KOOusvP8y22CR5a74gAEwNEZ2+15FFz1aq+9TASqJ3DnoPyMp93PSyQFfcpr63MEBZSi4Q1reOMdOydPW0o+8xG7TXvgtCcnvR5jpvJYqbSuq+lUTMFc//oqkGORpDAdk4HHYpH/6YjqjZI4y0jekq7UnR3cqJnoxV8yHu0pr9z5ukHfcUYBdKY5EfIOzATMY1yRz2jO84/JLHrWUz0qj98UJwvTYgau6X4/g9ubBBfaouhnV6OSdVR/WFxae/nlq/b84Qc=~1786983413245; bm_s=YAAQpYosMcPAJw6gAQAAhviCEAUT+CwlfiPMIDX1H2r5PphFrGeZlPO/zErQ+DxdgI1X03QdScAPAfKVmwl/A0pVpRDafONC7aeCVtMyZZsUPba8hK0Pkye4s+noxUZ40SZ/eLPaoGENuv/6GjUHzkK8dB3UgOQLu+8WoPGKe2PEpb0+Ai/1ebkwWgu/j7gIBhit+O1tkKAD8wx9+6OJXEmTQ2hqXt5H/HfQFpLXTnV5rJBe3zqUvZmoQVIQmeGnT2jMuxGas+pHPaU2uAVaO77+ytCNox5dK7TEAZQIzvbCZQYHQIzT104+COcK3ONqHjXug+FVxmc0mhRWLA1jNhnesg6vcbRv9RX8junMffJGn3RkOztnPYV6UVlX55SqKwq6pkYoVB8ZQrgVyxpOlZU1+gmYnFNOHpP2Roiw3XW0JjLo6sNzEqkJiBp3nBbKTAeFlSZAHxAZKqAWM5LqU+p3eC79sc8DZjBS6pb6CMayIXGqlF2631528RVaVXbSPrTuJT1CnpD1YplnfzxsIDgvU8OuDePz7YPZHZIdOdqcI1nC1jfAxSZ/34haOimZFce0to0RlXZQtZp/4+ifumYp3T3xLCVEWwaQcgb5IzJi88sGF8HG/nH4BdU9DGUIbDDGMvQlSvFX05aVF329Q6NvxOv/kJw/nvRhhU7ExMZsgk1hcIIa4FPJgNcwIb9M2yI/sAWn48Lq0Dx9aLS9xyUNbg2AatSIsqAvg9gqiD9t4fGQ3BZ7Gq2Hkio2Bllxa7mbGhkc6hpQPljd5TewHAknAD28KqT5vu+GcgAvsMvNhmVOP8mj/kemriBl6lNUEYKMs7Z6JkyDQsYe0/jxjteBQoCUHS/SNTJBXSzs3S0C8n6s4WKFS8uKLJm4cDtUeP/eNTwz2juINO+I6efJ8Uj8E/xMMtPkysZQN1Zf8FbQOEurje8zxS4F5RNVD4unJMaVJf1RR/RPRFFmd7w6pYLw6dYEye7RZbqymTZcC0uN9Z4/GuSKXHA577QdmtwssafCuOEhXHWsU6bf0Jidk7XcumYfhvF6uxyRn8H5gpMzXXQVvCxsw2uWkF811cc=; FCNEC=%5B%5B%22AKsRol-IFreiGARzkkwTYImFM33CHqoQIBs9OM34Ui9_Cr7IecMrPoXChCvAfw-23pAgocyofFgxD_c3RbsdT6nHMSBc42K7rds5JmSwmiIuHrxhdpWZrrx9l4lKVSChp_HJLopKcbo-c08P2MnjOS3l_XU4yB513A%3D%3D%22%5D%5D; _ga_5PY4KYQRFS=GS2.1.s1786983413$o6$g0$t1786983418$j55$l0$h0; bm_sv=9A82F768515B6634BA7B61809DDEFB29~YAAQpYosMSPJJw6gAQAA6FCDEAAFhQReFWCAT5L7BcETQlpDTISbyAPiPKMo/3AQ6WbiVFmt5Fk0Oyta+fb9FYk+mswAKpiIK1qxEXDQgJx2xwmRZJ9DTtRm2F38jD4sbyxiYMyVsT21fz9Js0cBoP2sLPxDek9uWpcMZ5SYcbVlzkkDRiG51Ijalac05bBhhcknIDpzDictd3A7SBR0uz8SOMnCFEXewB+M1vIuXvJhvPTf+4tH9PC/uRKPRYqYI0rH~1; RT="z=1&dm=justdial.com&si=a08c460d-21d2-41b9-a308-36edae6703ed&ss=msxfs8c8&sl=1&tt=1vr&rl=1&ld=1vr&nu=9y8m6cy&cl=mk2"',
    }

    params = {
        'searchReferer': 'gen|lst',
    }

    json_data = {
        'search': f'{search}',
        'city': f'{city}',
    }

    response = requests.post(
        'https://www.justdial.com/api/getLocationSuggestions',
        params=params,
        headers=headers,
        json=json_data,
    )

    if response.status_code == 200:
        return response.json()
    else:
        return {}


def human_pause(min_time=0.5, max_time=1.5):
    time.sleep(random.uniform(min_time, max_time))

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def ensure_chrome_running():
    if not is_port_in_use(9222):
        print("Chrome is not running on port 9222. Launching Chrome...")
        chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        user_data_dir = r"C:\Users\meetv\OneDrive\Desktop\just_dial_scraper\chrome-profile"
        
        chrome_args = [
            chrome_path,
            "--remote-debugging-port=9222",
            f"--user-data-dir={user_data_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-http2",
            "--disable-blink-features=AutomationControlled",
            '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]
        
        subprocess.Popen(chrome_args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        for _ in range(10):
            if is_port_in_use(9222):
                print("Chrome started successfully.")
                break
            time.sleep(1)
        else:
            print("Warning: Timed out waiting for Chrome to start on port 9222.")

def get_cookies(search,lat, lng, city="surat"):
    ensure_chrome_running()
    with sync_playwright() as p:

        browser = p.chromium.connect_over_cdp(
            "http://127.0.0.1:9222"
        )

        context = browser.contexts[0]

        page = context.new_page()

        # Setup listener to capture resultsPageListing requests
        captured_data = []

        def handle_request(req):
            if "resultsPageListing" in req.url:
                try:
                    captured_data.append({
                        "url": req.url,
                        "headers": dict(req.headers),
                        "json_data": req.post_data_json if req.post_data else {}
                    })
                except Exception:
                    pass

        page.on("request", handle_request)

        # Navigate with retry logic (Akamai/network can be slow)
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                page.goto(
                    "https://www.justdial.com/",
                    wait_until="domcontentloaded",
                    timeout=60000
                )
                break
            except Exception as nav_err:
                if attempt < max_retries:
                    print(f"Navigation attempt {attempt}/{max_retries} failed: {nav_err}. Retrying...")
                    time.sleep(3)
                else:
                    print(f"All {max_retries} navigation attempts failed. Raising error.")
                    page.close()
                    browser.close()
                    raise

        # 1. Click the location input, fill the city name, and select the first suggestion
        try:
            city_input = page.locator("#city-auto-sug").first
            city_input.click(force=True)
            city_input.fill("")
            city_input.type(city)
            
            # Wait for suggestion dropdown list to appear
            suggestion_item = page.locator("#sugcont li, #sugcont [role='option'], .react-autosuggest__suggestion, .react-autosuggest__suggestions-list li").first
            suggestion_item.wait_for(state="visible", timeout=8000)
            
            # Get all suggestions list elements
            suggestions_locator = page.locator("#sugcont li, #sugcont [role='option'], .react-autosuggest__suggestion, .react-autosuggest__suggestions-list li")
            suggestions = suggestions_locator.all()
            
            # Find the one that matches the city exactly (ignoring menu headers/detect locations)
            target_suggestion = None
            for sug in suggestions:
                text = sug.inner_text().strip()
                lines = [line.strip().lower() for line in text.split('\n') if line.strip()]
                if not lines:
                    continue
                if "recent locations" in lines[0] or "clear all" in lines[0] or "detect location" in lines[0]:
                    continue
                if lines[0] == city.lower():
                    target_suggestion = sug
                    break
            
            # Fallback 1: First suggestion that doesn't contain headers or detect location
            if not target_suggestion:
                for sug in suggestions:
                    text = sug.inner_text().strip()
                    lines = [line.strip().lower() for line in text.split('\n') if line.strip()]
                    if not lines:
                        continue
                    if "recent locations" in lines[0] or "clear all" in lines[0] or "detect location" in lines[0]:
                        continue
                    target_suggestion = sug
                    break
            
            # Fallback 2: The very first suggestion
            if not target_suggestion:
                target_suggestion = suggestions_locator.first
            
            print(f"Selecting suggestion: {target_suggestion.inner_text().strip()}")
            target_suggestion.click()
        except Exception as e:
            print("Error filling city or selecting suggestion:", e)

        # Wait a moment for page location changes to take effect
        time.sleep(3)

        # 2. Fill search input and select first suggestion to trigger search page navigation & API call
        request_headers = {}
        request_payload = {}
        api_url = ""

        if search:
            try:
                # Find search box (id="main-auto" or fallback as shown in the screenshot)
                search_input = page.locator("#main-auto, #srchbx, input[placeholder*='Search'], input[placeholder*='search']").first
                search_input.click(force=True)
                search_input.fill("")
                search_input.type(search)

                # Wait for main autocomplete suggestions to load
                search_suggestions_locator = page.locator("#main-auto-suggest li, #main-auto-suggest [role='option'], #react-autowhatever-1 li, .react-autosuggest__suggestion, .react-autosuggest__suggestions-list li")
                search_suggestions_locator.first.wait_for(state="visible", timeout=8000)

                # Get all search suggestions list elements
                suggestions = search_suggestions_locator.all()
                target_search_suggestion = None
                
                # Match exact search query ignoring casing
                for sug in suggestions:
                    text = sug.inner_text().strip()
                    lines = [line.strip().lower() for line in text.split('\n') if line.strip()]
                    if not lines:
                        continue
                    if lines[0] == search.lower():
                        target_search_suggestion = sug
                        break
                
                # Fallback: First suggestion in the list
                if not target_search_suggestion:
                    target_search_suggestion = search_suggestions_locator.first

                print(f"Selecting search suggestion: {target_search_suggestion.inner_text().strip()}")
                target_search_suggestion.click(force=True)

                # Wait for the results page to load and Akamai bot manager challenges to solve/validate cookies
                print("Waiting for page to stabilize and cookies to become trusted (Akamai challenge)...")
                page.wait_for_timeout(6000)

                # Process the captured API data
                if captured_data:
                    # Take the last captured request
                    api_info = captured_data[-1]
                    api_url = api_info["url"]
                    request_headers = api_info["headers"]
                    request_payload = api_info["json_data"]
                    
                    # Capture the validated cookies now
                    validated_cookies = context.cookies()

                    # Save the intercepted data to intercepted_api.json
                    intercepted_data = {
                        "url": api_url,
                        "headers": request_headers,
                        "json_data": request_payload,
                        "cookies": validated_cookies
                    }
                    with open('intercepted_api.json', 'w', encoding='utf-8') as f:
                        json.dump(intercepted_data, f, indent=4)
                    print("Saved intercepted API request and cookies to intercepted_api.json")
                else:
                    print("Warning: No resultsPageListing API call captured by listener.")

            except Exception as e:
                print("Error during search input or suggestion interception:", e)

        # Retrieve the final cookies before closing the browser context
        final_cookies = context.cookies()
        page.close()
        browser.close()

        response = {
            "status": 200, 
            "body": {
                "message": "Success",
                "api_url": api_url,
                "json_data": request_payload,
                "headers": request_headers
            }
        }
        return response, final_cookies

if __name__ == "__main__":
    response, cookies = get_cookies(
        search="Pest Control Services",
        lat=21.14204978942871,
        lng=72.7733383178711,
        city="surat"
    )

    print(response)
    cookies = {i['name'] : i['value'] for i in cookies}
    with open('cookies.json','w',encoding='utf-8') as f:
        json.dump(cookies,f,indent=4)