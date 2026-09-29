#!/usr/bin/env python3
"""Large monotonic visual target for the Pi's attached text console (no GUI).

Run on the Pi monitor's terminal, not an SSH terminal on a different screen.
Film the target and received dashboard image together; subtract the displayed
elapsed times in the same phone frame. No synchronized computer clocks needed.
"""
import argparse
import shutil
import sys
import time

DIGITS = {
 '0':('###','# #','# #','# #','###'), '1':('  #','  #','  #','  #','  #'),
 '2':('###','  #','###','#  ','###'), '3':('###','  #','###','  #','###'),
 '4':('# #','# #','###','  #','  #'), '5':('###','#  ','###','  #','###'),
 '6':('###','#  ','###','# #','###'), '7':('###','  #','  #','  #','  #'),
 '8':('###','# #','###','# #','###'), '9':('###','# #','###','  #','###'),
 '.':('   ','   ','   ','   ',' # '),
}

def screen(elapsed, width):
    value=f'{elapsed:09.3f}'
    digits=['  '.join(DIGITS[c][row] for c in value) for row in range(5)]
    if width >= 90:
        digits=[''.join(c*2 for c in row) for row in digits]
    flash='WHITE' if int(elapsed*4)%2 else 'BLACK'
    lines=['ASCENT / VISUAL LATENCY TARGET', '', *digits, '', f'{value} elapsed seconds',
           '20 updates/sec (50 ms steps); monitor scanout adds uncertainty.',
           'Record this target AND dashboard together. Subtract their times.',
           'Ctrl+C exits. No RC output.']
    content='\033[H'+''.join(line.center(width)+'\033[K\n' for line in lines)
    return content+('\033[47m' if flash=='WHITE' else '\033[40m')+' '*width+'\033[0m\033[J'

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds',type=int,default=600,help='Finite duration, default 10 minutes')
    args=parser.parse_args()
    if not 1<=args.seconds<=3600:parser.error('seconds must be 1..3600')
    if not sys.stdout.isatty():parser.error('Run on the attached monitor terminal')
    width=min(120,shutil.get_terminal_size().columns)
    start=time.monotonic();deadline=start
    try:
        print('\033[?1049h\033[?25l\033[2J',end='',flush=True)
        while time.monotonic()-start<args.seconds:
            print(screen(time.monotonic()-start,width),end='',flush=True)
            deadline+=.05
            if deadline<time.monotonic():deadline=time.monotonic()
            time.sleep(max(0,deadline-time.monotonic()))
    except KeyboardInterrupt:
        pass
    finally:
        print('\033[0m\033[?25h\033[?1049l',end='',flush=True)

if __name__=='__main__':main()
