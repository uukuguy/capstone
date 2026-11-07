# Gateway contract context reuse plan

1. Add failing tests for adapter-owned contract classification and connection-local
   reuse across tasks, including publication drift, grants, errors and budgets.
2. Add bounded metadata retention to DataGatewayAccess. Keep protocol recognition
   in DataGatewayMcp and prevent late old-publication observations from admission.
3. Stage frozen read-only sections and a compact index in NativeTaskRunner; reuse
   existing private workspace reads. Test the actual SDK launch/config seam.
4. Run focused adapter/relay/SDK checks, then canonical rebuild and the same real
   two-turn trial. Keep deployment identity distinct from branch/control commits.
5. Record measured results and scoped changes. Preserve existing root work. Any
   new CI run requires separate explicit approval; use focused local checks first.
