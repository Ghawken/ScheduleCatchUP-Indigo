ScheduleCatchUP for Indigodomo

Creates Actions (4 currently)

1 - Saves current schedule to file
2 - Load saved schedule and checks against current time - runs those schedules that have occured since
3 & 4 - inclues pausing and restarting Timers

Usage:

With your favourite Indigo UPS monitor.

Example:
Power Out:  (UPS on)
- set Save Schedule and Timers action

This will save to file the current schedule and state of running Timers

2-3 hours pass whilst Indigo is running on UPS.

Power Back On:
- set Load Schedule and Timers action

The plugin will reload the saved schedules, check what should have run and then run one schedule after another.
Paused timers will be restarted

Config Options:
Can select Schedules to ignore
& select time for check