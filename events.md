---
returned_object: evidence
when_to_use: Use this skill if user claims something happened, if you have a timeframe available it is always worth to validate events.
requires:
    - guess_time

link_generation_function: cma.get_events
utilized_systems:
    - cma
---

Remember that timeframe must have `utc.` prefix

Before doing anything with events first call cato_api_client.list_available_events(timeframe) and just print the return of this function. This will provide you values to use with filters.

To utilise events endpoint you must use 

cato_api_client.get_events(dimensions: list[dict], filters: list[dict], timeframe: str, timezone: str)

Dimensions and filters should be created as follows.

dimensions = [{"fieldName": "event_type"}, {"fieldName": "src_site_name"}]
filters = [{"fieldName": "event_type", "operator": "in", "values": ["Connectivity"]}]

as a result you get a list with fields

Here is the list of available operators operator: FilterOperator {between:exists, gt, gte, in, is, is_not, lt, lte, not_between, not_exists, not_in}

Here is the list of available fieldName options based on categories

all categories:
- event_type
- event_sub_type
- action:  (Firewall, QoS or LAG action)
- event_message:  (Cato's description of the event)

for connectivity related issues:
- socket_role:  (For Socket HA events, indicates if the Socket is primary or secondary)
- socket_interface:  (Name for Socket interface)

for urls_kwargs return exactly same parameters as provided to cato_api_client.get_events(dimensions: list[dict], filters: list[dict], timeframe: str, timezone: str)