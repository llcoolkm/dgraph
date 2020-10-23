#!/usr/bin/env python3
#
# fsgrowth - report the daily growth of filesystems through mail
#
# - Schedule in cron every hour or every day. Delta is given in seconds in report
# - Writes to history file and compare delta
# - Sends a report every time it's run with diff and delta
#   
# pip3 install matplotlib pandas pretty_html_table
# 
#------------------------------------------------------------------------------
# Imports {{{
import socket
import shutil
import io
import os
import pickle
import argparse
from datetime import datetime
# graph
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.style as style
from matplotlib import rcParams
# mail
import smtplib
from email.message import EmailMessage
from email.headerregistry import Address
from email.utils import make_msgid
from pretty_html_table import build_table

# }}}
# Config {{{
fs = '/omd/data/archive08'
environment = 'SEB'
hostname = socket.gethostname()
historyfile = '/tmp/fsgrowth.db'

# SMTP server
smtphost = 'smtp.sebot.local'
smtpport = 25
smtpfrom = 'fsgrowth@addpro.se'
smtprcvr = 'david.henden@addpro.se'

# }}}
# def main(): {{{
#------------------------------------------------------------------------------
def main():
    """Load history, collect data, save history, send an e-mail report"""

    # Load history
    history = loadhistory(args.import_file)

    # Collect data
    present = collectdata()

    # Append present to history
    present['delta'] = present['used'] - history.used.iloc[-1]
    data = history.reset_index().append(present, ignore_index=True)
    data.set_index('date', inplace=True)

    # Generate a graph
    graph = creategraph_pyplot(data)

    # Update history file - or not!
    if args.dont_update_history:
        if not args.quiet:
            print('Did not update history file')
    else:
        # Write history pickle
        pickle.dump(data, open(historyfile, 'wb'))
        print('Updated history file: {}'.format(historyfile))

    # Export
    if args.export_file:
        try:
            history.to_csv(args.export_file)
            print('Wrote export csv file: {}'.format(args.export_file))
        except Exception as e:
            print(e)

    # Fix the dataframe for reporting
    # Reverse it and drop boring columns
    data.reindex(index=data.index[::-1])
    data.drop(columns=['fs', 'avg'], inplace=True)
    
    # Send report
#    writereport(data, graph)
    mailreport(data, graph)

    return None


# }}}
# def collectdata(): {{{
#------------------------------------------------------------------------------
def collectdata():
    """Collect data from all file systems and return as an array"""

    now = datetime.now().replace(microsecond=0)

    try:
        [total, used, free] = map(lambda x: int(round(x / 1024 / 1024 / 1024)),
            shutil.disk_usage(fs))

        # Get pct
        if total == 0:
            pct = 0
        else:
            pct = round((used / total) * 100)

        fsvalues = {'date': now, 'fs': fs, 'total': total, 'used': used,
            'free': free, 'pct': pct}
    except Exception as e:
        print('ERROR collecting filesystem data: {}'.format(e))
        exit(-1)

    print('Collected data for filesystem: {}'.format(fs))

    return fsvalues


# }}}
#def creategraph_pyplot(data): {{{
#------------------------------------------------------------------------------
def creategraph_pyplot(data):
    """Plot a beautiful graph and return a png in a string"""

    data['avg'] = data.free.rolling(7).mean().shift(-3)
    data['weekday'] = data.index.weekday
    data['weekend'] = [True if value >=5 else False for value in data.weekday]

    total_mean = round(data.delta.mean())
    positive_mean = round(data.delta.where(data.delta.ge(0)).mean())

    # Create the plots
    fig, ax = plt.subplots(figsize=(12,4))
    plt.gcf().subplots_adjust(bottom=0.20)
    plt.title('Free GB by day: {}'.format(fs), fontsize=16)

    # Free
    plt.plot(mdates.date2num(list(data.index)), data.free, linewidth=3, color='#30a2da')
#    # Rolling 7day average
#    plt.plot(mdates.date2num(list(data.index)), data.avg, linewidth=3, color='#e5ae38')
    # Delta change
    plt.bar(mdates.date2num(list(data.index)), data.delta, alpha=.5,
        align='center',
        color=['#6d904f' if value >= 0 else '#fc4f30' for value in data.delta])

    ax.grid(b=True, which='major', color='gray', linestyle='-', alpha=.3)
    [ax.spines[x].set_visible(False) for x in ['top', 'right', 'bottom', 'left']]
    style.use('fivethirtyeight')
    ax.set_facecolor('#f0f0f0')
    fig.set_edgecolor('#f0f0f0')

    # Set the x axis
    plt.xticks(rotation=25, fontsize=12)
    ax.axhline(y = 0, color = 'black', linewidth = 1.3, alpha = .7)
    ax.xaxis_date()
    ax.xaxis.label.set_visible(False)
    ax.xaxis.set_major_locator(mdates.DayLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
    ax.set_xticks(ax.get_xticks()[1:-1])

    # Set the y axis
    plt.yticks(fontsize=12)
    bottom = int(round(ax.get_yticks()[0]))
    top = int(round(ax.get_yticks()[-1]))
    ystep = int(round((top - bottom) / 10))
    yrange = list(range(bottom, top, ystep))
    ax.set_yticks(yrange[1:])
    ax.set_ylabel('GB', fontsize=14)
     
    # Put a text box in upper right corner
    props = dict(boxstyle='square', facecolor='wheat', alpha=.6, pad=.5)
    ax.text(ax.get_xticks()[-1]-.5, top - 2 * ystep,
        'Mean growth: {}\nPositive mean growth: {}'.
        format(total_mean, positive_mean),
        fontsize=14, va='center', ha='right', bbox=props)

    # Save
    graph = io.BytesIO()
    plt.savefig(graph, format='png', dpi=72)
    graph.seek(0)

    return graph.read()


#}}}
# def loadhistory(importfile) {{{
#------------------------------------------------------------------------------
def loadhistory(importfile):
    """Load history from pickle or csv"""
    history = {}

    # Import csv...
    if importfile:
        try:
            history = pd.read_csv(importfile, parse_dates=['date'], index_col=['date'])
            if not args.quiet:
                print('Imported csv file {} with {} data points'
                    .format(importfile, len(history))
        except Exception as e:
            print('Unable to import csv file: {}'.format(e))
            exit(-1)

    # ...or try to load a pickle
    else:
        if os.path.isfile(historyfile):
            try:
                history = pickle.load(open(historyfile, 'rb'))
                if not args.quiet:
                    print('Imported history file {} with {} data points}'
                        .format(historyfile, len(history)))
            except Exception as e:
                print('Unable to load history file: {}'.format(e))
                exit(-1)
        else:
            if not args.quiet:
                print('No history loaded')

    return history


# }}}
# def writereport(data): {{{
#------------------------------------------------------------------------------
def writereport(table, graph):

    html_table = build_table(table.reset_index(), 'grey_light', font_size='small', font_family='Verdana')
    html="""\
<html>
  <body>
    <center>
      <table width="100%" border="0" cellpadding="0" cellspacing="0" bgcolor="#FFFFFF">
        <tr>
          <td align="center" valign="top">
            <div><p><img src="graph.png"></p></div>
            <div><p>{table}</p></div>
            <div><p>/fsgrowth e-mail reporter on {hostname}</p></div>
          </td>
        </tr>
      </table>
  </body>
</html>
""".format(hostname=hostname, table=html_table)

    with open('graph.png', 'wb') as f:
        f.write(graph)
    f.close()

    reportfile = 'report.html'
    with open(reportfile, 'w') as f:
        f.write(html)
    f.close()

    if not args.quiet:
        print('Wrote report to disk: {}'.format(reportfile))

    return None


#}}}
# def mailreport(data): {{{
#------------------------------------------------------------------------------
def mailreport(data, graph):
    """Build the e-mail report and send it"""

    html_table = build_table(data.reset_index(), 'grey_light', font_size = 'small', font_family = 'Verdana')

    # Create an e-mail
    message = EmailMessage()
    message['From'] = Address(smtpfrom)
    message['To'] =  Address(smtprcvr)
    message['Subject'] = '{}: File system report from {}'.format(environment,
        hostname)

    # Attach a body and our image
    img_cid = make_msgid()
    message.add_alternative("""\
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
    <head>
        <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
        <title></title>
        <style></style>
    </head>
    <body>
        <table border="0" cellpadding="0" cellspacing="0" height="100%" width="100%" id="bodyTable">
            <tr>
                <td align="center" valign="top">
                    <table border="0" cellpadding="20" cellspacing="0" width="600" id="emailContainer">
                        <tr>
                            <td align="center" valign="top">
                                <tr><p><img src="cid:{img_cid}"></p></tr>
                                <tr><p>{table}</p></tr>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
</html>
""".format(hostname=hostname, table=html_table, img_cid=img_cid[1:-1]), subtype='html')
    message.get_payload()[0].add_related(graph, 'image', 'png', cid=img_cid)

    # Send it
    smtpserver = None
    try:
        smtpserver = smtplib.SMTP(smtphost, smtpport)
        smtpserver.ehlo()
        smtpserver.sendmail(smtpfrom, smtprcvr, message.as_string())
    except Exception as e:

        print('ERROR: Unable to send e-mail: {}'.format(e))
    finally:
        if smtpserver:
            smtpserver.close() 
            print('e-mail sent to {}'.format(smtprcvr))

    return None


# }}}
# __main__ {{{
#------------------------------------------------------------------------------
if __name__ == '__main__':
    """Parse arguments and call main"""

    parser = argparse.ArgumentParser(description='fsgrowth')
    parser.add_argument('--days', '-d', type=int, default=7, help='Number of days to include in report')
    parser.add_argument('--export-file', '-e', type=str, help='Export data to this csv file instead of collecting new data and reporting')
    parser.add_argument('--import-file', '-i', type=str, help='Import historical data from this csv file instead of default')
    parser.add_argument('--dont-update-history', '-H', action='store_true', help='Don\'t update history file. Good for testing')
    parser.add_argument('--quiet', '-q', action='store_true', help='Be quiet. Dont print any output except for errors. Good for crontab')
    args = parser.parse_args()
    main()

# }}}
