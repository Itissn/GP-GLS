"""Recompute descriptive results from the archived workbook; do not rerun GP-GLS."""
from pathlib import Path
import hashlib
import json
import math
import csv
import statistics
import openpyxl
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'results/Final Result.xlsx'


def main():
    sheet=openpyxl.load_workbook(SOURCE,read_only=True,data_only=True).worksheets[0]
    rows=list(sheet.values)
    observations=[];issues=[]
    for excel_row,row in enumerate(rows,1):
        if not str(row[0]).strip().startswith('X-'):continue
        name=str(row[0]).strip(); bks=float(row[1]); kgls=float(row[3])
        values=[float(row[i]) for i in range(7,37,2)]
        gaps=[(value-bks)/bks for value in values]
        avg=statistics.mean(values)
        if not math.isclose(avg,float(row[5]),rel_tol=1e-10):
            issues.append({'sheet':'Sheet1','row':excel_row,'field':'GPGLS_A','stored':row[5],'recomputed':avg})
        for i,gap in enumerate(gaps):
            stored=float(row[8+2*i])
            if not math.isclose(gap,stored,rel_tol=1e-9,abs_tol=1e-12):
                issues.append({'sheet':'Sheet1','row':excel_row,'field':f'Gap_{i+1}','stored':stored,'recomputed':gap})
        observations.append({'instance':name,'bks':bks,'kgls_objective':kgls,'kgls_gap':(kgls-bks)/bks,
                             'gpgls_mean_objective':avg,'gpgls_mean_gap':(avg-bks)/bks,
                             **{f'result_{i+1}_gap':g for i,g in enumerate(gaps)}})
    footer=rows[-1]
    for i in range(15):
        mean=statistics.mean(r[f'result_{i+1}_gap'] for r in observations)
        stored=float(footer[8+2*i])
        if not math.isclose(mean,stored,rel_tol=1e-9,abs_tol=1e-12):
            issues.append({'sheet':'Sheet1','row':len(rows),'field':f'footer_gap_{i+1}','stored':stored,'recomputed':mean})
    out=ROOT/'results/derived';out.mkdir(parents=True,exist_ok=True)
    with (out/'instance_summary.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(observations[0]));writer.writeheader();writer.writerows(observations)
    with (out/'reconciliation_issues.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=['sheet','row','field','stored','recomputed']);writer.writeheader();writer.writerows(issues)
    summary={'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'instances':len(observations),
             'recorded_result_columns':15,'gpgls_mean_gap_pct':statistics.mean(r['gpgls_mean_gap'] for r in observations)*100,
             'kgls_mean_gap_pct':statistics.mean(r['kgls_gap'] for r in observations)*100,
             'reconciliation_issue_count':len(issues),'algorithm_rerun':False,
             'scope':'Descriptive summary of archived values, not a controlled rerun or significance claim.'}
    (out/'summary.json').write_text(json.dumps(summary,indent=2))
    (ROOT/'assets').mkdir(exist_ok=True)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11})
    fig,ax=plt.subplots(figsize=(9,6),facecolor='#F5F7FA')
    x=[r['kgls_gap']*100 for r in observations];y=[r['gpgls_mean_gap']*100 for r in observations]
    limit=max(x+y)*1.08
    ax.scatter(x,y,color='#137A86',alpha=.75,s=34,edgecolors='white',linewidths=.5)
    ax.plot([0,limit],[0,limit],ls='--',lw=1,color='#82909C',label='Equal recorded gap')
    ax.set(xlim=(0,limit),ylim=(0,limit),xlabel='KGLS(10) gap to recorded BKS (%)',ylabel='GPGLS mean gap to recorded BKS (%)')
    ax.spines[['top','right']].set_visible(False);ax.grid(alpha=.15);ax.legend(frameon=False,fontsize=9)
    fig.suptitle('GP-GLS | Archived benchmark results',x=.11,ha='left',fontsize=18,weight='bold',color='#173146')
    ax.set_title(f'{len(observations)} instances · recomputed from objective values · lower gap is better',loc='left',fontsize=10,pad=16)
    fig.text(.11,.015,'Source: Final Result.xlsx. Algorithm not rerun; runtime/seed parity unverified. See reconciliation_issues.csv.',fontsize=8,color='#536575')
    fig.tight_layout(rect=[0,.04,1,.95]);fig.savefig(ROOT/'assets/benchmark_results.png',dpi=150);plt.close(fig)
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
