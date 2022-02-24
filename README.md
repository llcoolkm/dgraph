# dgraph

Simple graph tool that collects a value from a command and generates a graph with delta change. Can output an image file to a directory or e-mail a report.

## Prerequisites

Install python modules

```
python3 -m pip install --upgrade pandas matplotlib pretty_htnml_table
```

## How to run

Edit the script and change the email parameters. You should run it once per day to collect stats. Report can be sent at the same time or scheduled separately, for example in the morning or weekly. Run it once manually first to see that everything works.

```
./dgraph.py
```

Install it into crontab:
```
echo '00 23 * * * root /opt/scripts/dgraph/dgraph.py -H /tmp/dgraph.csv --update' > /etc/cron.d/dgraph
echo '00 08 * * * root /opt/scripts/dgraph/dgraph.py -H /tmp/dgraph.csv --report' >> /etc/cron.d/dgraph

```

or run it as a systemd timer:
[TODO]

If everything works add --quiet. The first day will contain an empty graph and also a 0 delta change.

## TODO

- Multi-value graph
- Predictions
- Moving average

