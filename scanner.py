import os, json, time, urllib.request, urllib.parse, statistics
from datetime import datetime, timezone

BASE="https://indodax.com/api"
def get(url):
    req=urllib.request.Request(url,headers={"User-Agent":"IndodaxResearchScanner/1.0"})
    with urllib.request.urlopen(req,timeout=25) as r:return json.load(r)
def candles(pair,interval):
    end=int(time.time()); start=end-86400*12
    q=urllib.parse.urlencode({"pair":pair,"tf":interval,"from":start,"to":end})
    data=get(BASE+"/tradingview/history?"+q)
    if data.get("s")!="ok":return []
    return [{"t":t,"c":float(c),"v":float(v)} for t,c,v in zip(data["t"],data["c"],data["v"]) if float(c)>0]
def ema(values,n):
    if not values:return 0
    e=values[0];k=2/(n+1)
    for v in values[1:]:e=v*k+e*(1-k)
    return e
def rsi(values,n=14):
    if len(values)<n+1:return 50
    diff=[values[i]-values[i-1] for i in range(-n,0)]
    gains=sum(max(x,0) for x in diff)/n;loss=sum(max(-x,0) for x in diff)/n
    return 100 if loss==0 else 100-100/(1+gains/loss)
def evaluate(pair,tf):
    rows=candles(pair,tf)
    if len(rows)<55:return None
    close=[x["c"] for x in rows];vol=[x["v"] for x in rows]
    price=close[-1];trend=ema(close[-50:],20)>ema(close[-50:],50)
    momentum=ema(close[-30:],12)-ema(close[-30:],26)
    prev=ema(close[-31:-1],12)-ema(close[-31:-1],26)
    rv=vol[-1]/max(statistics.mean(vol[-21:-1]),1e-12)
    strength=rsi(close)
    score=20+int(trend)*25+int(momentum>prev)*20+int(rv>1.5)*15+int(45<=strength<=68)*20
    risk="TINGGI" if strength>75 or rv>8 else "SEDANG"
    status="BUY WATCH" if score>=75 and risk!="TINGGI" else "WAIT" if score>=50 else "AVOID"
    return {"pair":pair,"price":price,"score":score,"rsi":round(strength,1),"volume_ratio":round(rv,2),"risk":risk,"status":status,"support":min(close[-20:]),"resistance":max(close[-20:])}
def send(message):
    token=os.getenv("TELEGRAM_BOT_TOKEN");chat=os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("Telegram secrets belum tersedia; hasil hanya di log.");return
    data=urllib.parse.urlencode({"chat_id":chat,"text":message,"disable_web_page_preview":"true"}).encode()
    req=urllib.request.Request("https://api.telegram.org/bot"+token+"/sendMessage",data=data)
    with urllib.request.urlopen(req,timeout=25) as response:print("Telegram HTTP",response.status)
def main():
    raw=get(BASE+"/pairs")
    markets=raw if isinstance(raw,list) else raw.get("pairs",[])
    pairs=list(dict.fromkeys(x["ticker_id"].lower().replace("_","") for x in markets if isinstance(x,dict) and x.get("ticker_id","").upper().endswith("_IDR")))
    print("Pasangan IDR:",len(pairs))
    results={}
    for tf,name in [("15","CEPAT 15m–4j"),("240","SWING 1–7h")]:
        ranked=[]
        for pair in pairs:
            try:
                item=evaluate(pair,tf)
                if item:ranked.append(item)
            except Exception as exc:print("SKIP",pair,tf,str(exc)[:120])
            time.sleep(.18)
        ranked.sort(key=lambda x:x["score"],reverse=True)
        results[name]=ranked[:10]
        print(name,"dievaluasi:",len(ranked))
    with open("report.json","w") as f:json.dump({"generated_utc":datetime.now(timezone.utc).isoformat(),"results":results},f,indent=2)
    lines=["📊 INDODAX AI SCANNER | PAPER ONLY",datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")]
    for name,items in results.items():
        lines.append("\n"+name)
        for x in items:lines.append(f'{x["pair"].upper()} | {x["status"]} | skor {x["score"]} | RSI {x["rsi"]} | risiko {x["risk"]}')
    send("\n".join(lines)[:3900])
if __name__=="__main__":main()
