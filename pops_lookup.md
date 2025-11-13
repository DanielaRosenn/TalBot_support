---
returned_object: entity
when_to_use: Use this skill if user mentions connectivity issues and you have identified sites to verify. 
requires: 
    - sites_lookup
utilized_systems:
    - hub
link_generation_function: hub.get_site_pops
---

To execute this skill you need a site to be provided to you. For every site in the query execute

cato_hub_client.get_site_pops(site_name) - RUN ONLY THIS FUNCTION NOTHING MORE

Site names must be lowercase and spaces replaced with _, e.g. Warsaw Palace becomes warsaw_palace

and as evidences return only POPs do not return sites. Exclude isp_ip and interface_id from this representation

As url_kwargs return {"site_name": site_name}