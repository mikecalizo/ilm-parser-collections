# ilm-parser-collections
Collections of Python scripts for reading ILM policies

1. Make sure that _cat/commercial/ilm_policy.json is in the same folder as the code
2. run python3.10 ilm-policy-parser-mike.py
3. Reports of the ILM policy should look like this

ython3.10 ilm-policy-parser-mike.py
Index Name                                                                       ILM Policy                Retention  Phase     
----------------------------------------------------------------------------------------------------------------------------------
.ds-.logs-deprecation.elasticsearch-default                                      .deprecation-indexing-ilm-policy 30d        delete    
.ds-.fleet-actions-results                                                       .fleet-actions-results-ilm-policy 90d        delete    
.ds-ti-sentinelone.process_hash-dev                                              365-days-default          365d       delete    
.ds-tdh-browser_extension.metadata-prod                                          365-days-default          365d       delete    
.ds-tdh-whois_process-dev                                                        365-days-default          365d       delete    
.ds-tdh-whois.process-prod                                                       365-days-default          365d       delete    
.ds-ti-cloudflare.domain-prod                                                    365-days-default          365d       delete    
.ds-tdh-brew_packages.external-prod                                              365-days-default          365d       delete    
.ds-tdh-whois_sequence-prod                                                      365-days-default          365d       delete    
.ds-tdh-browser_extension.metadata-dev                                           365-days-default          365d       delete    
.ds-tdh-domain.whois-prod                                                        365-days-default          365d       delete    
.ds-tdh-whois.process-s1                                                         365-days-default          365d       delete    
.ds-tdh-domain.whois-dev                                                         365-days-default          365d       delete    
consumption-2025.04.01                                                           consumption               365d       delete    
.ds-logs-filebeat.errors-canva-audit                                             filebeat-ilm              30d        delete    
.ds-logs-filebeat.errors-vpcflow                                                 filebeat-ilm              30d        delete    
