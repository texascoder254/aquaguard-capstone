# AquaGuard authorization policy (OPA / Rego). The alpha evaluates the same rules
# in-process (app/policy.py); deploying OPA as a sidecar is tracked technical debt.
package aquaguard.authz

default allow := false

allow if {
    input.action == "readings:write"
    input.principal.role == "simulator"
    input.resource.simulator_user_id == input.principal.user_id
}

allow if {
    input.action in {"readings:read", "messages:write", "cases:open", "feedback:write", "transcript:read"}
    input.principal.role == "customer"
    input.resource.client_id == input.principal.client_id
}

allow if {
    input.action in {"readings:read", "cases:read", "cases:reply", "transcript:read"}
    input.principal.role == "agent"
    input.resource.client_id in input.principal.scopes
}
