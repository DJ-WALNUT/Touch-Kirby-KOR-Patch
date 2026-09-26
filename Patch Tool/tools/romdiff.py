import struct, sys, os
sys.stdout.reconfigure(encoding='utf-8')

def load(path):
    d=open(path,'rb').read()
    fnto,fnts,fato,fats=struct.unpack_from('<IIII',d,0x40)
    fat=[struct.unpack_from('<II',d,fato+i*8) for i in range(fats//8)]
    files=[]
    def sub(did,pre):
        off,ff,par=struct.unpack_from('<IHH',d,fnto+did*8)
        p=fnto+off; fid=ff
        while True:
            t=d[p]; p+=1
            if t==0: break
            if t<0x80:
                n=d[p:p+t].decode('ascii','replace'); p+=t
                files.append((pre+n,fid)); fid+=1
            else:
                l=t&0x7F; n=d[p:p+l].decode('ascii','replace'); p+=l
                s=struct.unpack_from('<H',d,p)[0]; p+=2
                sub(s&0xFFF,pre+n+'/')
    sub(0,'/')
    m={}
    for n,fid in files:
        if fid<len(fat):
            s,e=fat[fid]; m[n]=d[s:e]
    return m

jp=load(sys.argv[1]); us=load(sys.argv[2])
print(f'JP files={len(jp)}  US files={len(us)}')

onlyjp=sorted(set(jp)-set(us)); onlyus=sorted(set(us)-set(jp))
print(f'\nJP only ({len(onlyjp)}):'); [print('   ',x) for x in onlyjp[:30]]
print(f'\nUS only ({len(onlyus)}):'); [print('   ',x) for x in onlyus[:30]]

common=sorted(set(jp)&set(us))
diff=[n for n in common if jp[n]!=us[n]]
print(f'\ncommon={len(common)}  differing={len(diff)}  identical={len(common)-len(diff)}')
print(f'\n--- differing files (localized assets) ---')
tot=0
for n in diff:
    a,b=len(jp[n]),len(us[n]); tot+=max(a,b)
    mark='SIZE' if a!=b else 'same'
    print(f'  {n:<48} JP={a:>9,} US={b:>9,}  [{mark}]')
print(f'\n  total differing bytes (max) = {tot:,}')
