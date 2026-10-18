#!/usr/bin/env python3
"""Korean stock screener: relative strength, foreign/pension flows, 5/20 cross under 200 MA.
Usage: python screener.py --date 2026-10-16 --market ALL --output results.csv
Requires: pip install pykrx pandas numpy
"""
import argparse
import datetime as dt
import logging
import time
from pathlib import Path
import pandas as pd
from pykrx import stock

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

def get_close_frame(ticker, start, end):
    frame = stock.get_market_ohlcv_by_date(start, end, ticker, adjusted=True)
    if frame is None or frame.empty or '종가' not in frame:
        return pd.DataFrame()
    return frame.sort_index()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--date', default=dt.date.today().strftime('%Y-%m-%d'))
    parser.add_argument('--market', choices=['ALL','KOSPI','KOSDAQ'], default='ALL')
    parser.add_argument('--output', default='results.csv')
    parser.add_argument('--delay', type=float, default=0.12)
    args = parser.parse_args()
    target = pd.Timestamp(args.date)
    end = target.strftime('%Y%m%d')
    start = (target - pd.Timedelta(days=450)).strftime('%Y%m%d')
    benchmark = stock.get_index_ohlcv_by_date(start, end, '1028')  # KOSPI 200
    if benchmark is None or benchmark.empty or target not in benchmark.index:
        raise RuntimeError('KOSPI200 기준일 데이터가 없습니다. 거래일 또는 데이터 공급 상태를 확인하세요.')
    benchmark = benchmark.sort_index()
    if len(benchmark.loc[:target]) < 21:
        raise RuntimeError('KOSPI200 20거래일 비교 데이터 부족')
    bm_return = float(benchmark.loc[target, '종가'] / benchmark.loc[:target, '종가'].iloc[-21] - 1)
    markets = ['KOSPI','KOSDAQ'] if args.market == 'ALL' else [args.market]
    tickers = sorted(set(sum((stock.get_market_ticker_list(end, market=m) for m in markets), [])))
    logging.info('기준일 %s / 전체 %s종목', args.date, len(tickers))
    technical = []
    failures = []
    for i, ticker in enumerate(tickers, 1):
        try:
            df = get_close_frame(ticker, start, end)
            if target not in df.index or len(df.loc[:target]) < 201:
                failures.append((ticker, '가격 데이터 부족')); continue
            df = df.loc[:target].copy()
            close = df['종가'].astype(float)
            ma5 = close.rolling(5).mean(); ma20 = close.rolling(20).mean(); ma200 = close.rolling(200).mean()
            if not (close.iloc[-1] < ma200.iloc[-1] and ma5.iloc[-2] <= ma20.iloc[-2] and ma5.iloc[-1] > ma20.iloc[-1]):
                continue
            ret20 = float(close.iloc[-1]/close.iloc[-21]-1)
            # Relative strength ratio (stock / benchmark) must also be increasing over 20 sessions.
            bm = benchmark['종가'].reindex(df.index).ffill()
            rs = close / bm
            if not (ret20 > bm_return and rs.iloc[-1] > rs.iloc[-21]):
                continue
            volume = df['거래량'].astype(float)
            technical.append(dict(기준일=args.date, 종목코드=ticker, 종목명=stock.get_market_ticker_name(ticker), 종가=int(close.iloc[-1]), MA5=round(ma5.iloc[-1],2), MA20=round(ma20.iloc[-1],2), MA200=round(ma200.iloc[-1],2), 종목20일수익률_pct=round(ret20*100,2), 코스피200_20일수익률_pct=round(bm_return*100,2), 초과수익률_pct=round((ret20-bm_return)*100,2), 거래량비율=round(volume.iloc[-1]/volume.iloc[-20:].mean(),2) if volume.iloc[-20:].mean() else None))
        except Exception as exc:
            failures.append((ticker, str(exc)))
        finally:
            time.sleep(args.delay)
        if i % 100 == 0: logging.info('%d/%d 처리', i, len(tickers))
    logging.info('기술적 조건 통과 %d종목', len(technical))
    # Take exactly 10 available trading sessions ending at target for flows.
    days = list(benchmark.loc[:target].index[-10:])
    if len(days) < 10: raise RuntimeError('수급 비교 거래일 부족')
    results = []
    for candidate in technical:
        ticker = candidate['종목코드']
        try:
            flows = stock.get_market_trading_value_by_date(days[0].strftime('%Y%m%d'), end, ticker, detail=True)
            if flows is None or flows.empty: raise ValueError('수급 데이터 없음')
            flows = flows.sort_index().reindex(days)
            if flows.isna().any().any(): raise ValueError('수급 데이터 누락')
            foreign_col = next((c for c in ['외국인','외국인합계'] if c in flows.columns), None)
            pension_col = next((c for c in ['연기금','연기금등','연기금 등'] if c in flows.columns), None)
            if not foreign_col or not pension_col: raise ValueError('외국인/연기금 상세 열 없음')
            fprev, frecent = int(flows[foreign_col].iloc[:5].sum()), int(flows[foreign_col].iloc[5:].sum())
            pprev, precent = int(flows[pension_col].iloc[:5].sum()), int(flows[pension_col].iloc[5:].sum())
            if not (frecent > 0 and frecent > fprev and precent > 0 and precent > pprev): continue
            candidate.update(외국인_직전5일_억원=round(fprev/1e8,2), 외국인_최근5일_억원=round(frecent/1e8,2), 연기금_직전5일_억원=round(pprev/1e8,2), 연기금_최근5일_억원=round(precent/1e8,2), 거래량가점=candidate['거래량비율'] is not None and candidate['거래량비율'] >= 1.5)
            results.append(candidate)
        except Exception as exc:
            failures.append((ticker, '수급: '+str(exc)))
        finally: time.sleep(args.delay)
    cols = ['기준일','종목코드','종목명','종가','MA5','MA20','MA200','종목20일수익률_pct','코스피200_20일수익률_pct','초과수익률_pct','외국인_직전5일_억원','외국인_최근5일_억원','연기금_직전5일_억원','연기금_최근5일_억원','거래량비율','거래량가점']
    out = pd.DataFrame(results, columns=cols)
    if not out.empty: out = out.sort_values(['거래량가점','초과수익률_pct'],ascending=False)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.output,index=False,encoding='utf-8-sig')
    errorfile = str(Path(args.output).with_suffix('.errors.csv'))
    pd.DataFrame(failures,columns=['종목코드','오류']).to_csv(errorfile,index=False,encoding='utf-8-sig')
    logging.info('최종 %d종목, 실패/미확인 %d종목, 결과 %s, 오류 %s',len(out),len(failures),args.output,errorfile)
    if failures: logging.warning('데이터 누락이 있어 전체 시장에 대한 완전한 판정은 아닙니다.')

if __name__ == '__main__': main()
