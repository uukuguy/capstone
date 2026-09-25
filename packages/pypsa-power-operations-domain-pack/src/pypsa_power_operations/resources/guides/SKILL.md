# PyPSA Power Operations

The application hands an immutable model revision to this Pack. Use `operations.dispatch` for fixed dispatch, `operations.commitment` for a registered committable model, `operations.security_dispatch` for the registered outage set, `operations.rolling_dispatch` for the registered storage horizon, and `operations.congested_opf` for registered branch flows and nodal prices. Use `operations.ac_validate` only after a dispatch result. Cite the returned result and evidence references for numerical claims.
