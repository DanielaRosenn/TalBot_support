---
returned_object: time_frame
when_to_use: Use this skill to gather more detailed time information about the ticket.
requires:
    - sites_lookup
utilized_systems: []
disable_code_interpreter : True
---

First you need to decide in which timezone the analysis should be done. If the user doesn't mention timezone directly default to Europe/London. Please return timezone in IANA time zone format

You have to return a potential timeframes which support engineers must take a look. Again if there is no indication of any specific timeframe return an empty list. Always add a buffor of few minutes before and few minutes after.

<timeframe_instruction>
Enter the time frame for the data that the query returns. The argument is in the format <type>.<time value> This argument is mandatory.

The time frame combines a start and end date in the format utc.YY-MM-DD/hh:mm:ss

You must enter all the date and time values for the argument. For example:

timeFrame = utc.2020-02-{11/04:50:00--21/04:50:00} shows 10 days of analytics data from February 11, 2020 4:50:00 am to February 21, 2020 4:50:00 am
timeFrame = utc.2020-02-11/{04:50:15--16:50:15} shows 12 hours of analytics data on February 11, 2020, from 4:50:15 am to 16:50:15 pm
timeFrame = utc.2020-{02-11/04:50:00--04-11/04:50:00} shows 2 months of analytics data from February 11, 2020 4:50:00 am to April 11 4:50:00 am
timeFrame = utc.{2019-10-01/04:50:00--2020/02-01/04:50:00} shows 4 months of analytics data from October 1, 2019 4:50:00 am to February 11 4:50:00 am

ALWAYS ADD BRACES TO THE RETURNED TIMEFRAME
</timeframe_instruction

Always return just one timeframe to be analyzed - but anyway return it in a list.