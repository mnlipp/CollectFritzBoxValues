# Collect Fritz!Box Values (for graphite)

This is not a sophisticated program. Consider this to be script that 
you can adapt for your own purposes.

The program connects to a Fritz!Box Cable and executes an endless loop
that reads the cable modem values and writes them to 
[graphite](https://graphiteapp.org/).

Invoke the program with a YAML configuration file (mandatory). The
sample shows the built-in defaults.

```yml
fritzbox:
  ip: 192.168.178.1
  user: graphite
  password: none

graphite:
  server: localhost
  port: 2004

interval: 5
```

Usually, you don't need this data -- unless something goes wrong.
I wrote the program in order to document the problems that I have 
with my upstream connection. Still to be solved...