"""Runtime Enforcement Middleware and Audit for Guardrails."""

from typing import Any
from aip.guardrails.engine import GuardrailEngine
from aip.guardrails.decisions import PolicyRequest
from aip.guardrails.models import GuardrailEffect
from aip.guardrails.errors import GuardrailEnforcementError
from aip.contracts.models import AgentSpecification
from aip.app_context import ctx
from aip.guardrails.action import canonical_action_hash

async def _audit_and_enforce(tool_name: str, args: dict[str, Any], spec: AgentSpecification) -> None:
    from aip.guardrails.identity import get_execution_identity, AgentExecutionIdentity
    identity = get_execution_identity()
    if not identity:
        import uuid
        identity = AgentExecutionIdentity(
            agent_id=spec.spec_id,
            execution_id=str(uuid.uuid4()),
            project_id=spec.agent.org_id,
            organization_id=spec.agent.org_id,
            environment="unknown"
        )
    # Module 8: Populate Context from Application Data
    context = {
        "project_id": spec.agent.org_id,
        "agent_id": spec.spec_id
    }
    try:
        snap = ctx.graph.load_snapshot(spec.agent.org_id)
        # Add basic project ontology entities as context if needed, or project metadata
        if "environment" in snap.metadata:
            context["environment"] = snap.metadata["environment"]
    except Exception:
        pass

    req = PolicyRequest(
        identity=identity,
        tool=tool_name,
        arguments=args,
        context=context
    )
    
    from aip.guardrails.engine import GuardrailEngine
    
    try:
        # Module 12: Resolve applicable policies dynamically
        policies, policy_version = ctx.policy_resolver.resolve(identity)
        engine = GuardrailEngine(policies)
        decision = engine.evaluate(req)
    except Exception as exc:
        policy_version = "error"
        ctx.event_bus.emit(
            type="guardrail.decision",
            source="guardrail_engine",
            message=f"Guardrail EVALUATION FAILED for {tool_name}: {exc}",
            payload={
                "agent_id": identity.agent_id,
                "project_id": identity.project_id,
                "execution_id": identity.execution_id,
                "policy_version": policy_version,
                "tool": tool_name,
                "decision": "error",
                "error": str(exc),
            }
        )
        raise GuardrailEnforcementError(f"Guardrail evaluation failed unexpectedly: {exc}")

    ctx.event_bus.emit(
        type="guardrail.decision",
        source="guardrail_engine",
        message=f"Guardrail {decision.decision.value} for {tool_name}",
        payload={
            "agent_id": identity.agent_id,
            "project_id": identity.project_id,
            "execution_id": identity.execution_id,
            "policy_version": policy_version,
            "tool": tool_name,
            "decision": decision.decision.value,
            "guardrail_id": decision.guardrail_id,
            "reason": decision.reason,
        }
    )
    from aip.validation.evidence import append_guardrail_decision
    append_guardrail_decision(
        identity.execution_id,
        {
            "source": "native_middleware",
            "tool": tool_name,
            "decision": decision.decision.value,
            "reason": decision.reason,
            "guardrail_id": decision.guardrail_id,
        },
    )

    if decision.decision == GuardrailEffect.DENY:
        raise GuardrailEnforcementError(f"Action denied: {decision.reason}")
    if decision.decision == GuardrailEffect.REQUIRE_APPROVAL:
        ahash = canonical_action_hash(identity.execution_id, identity.agent_id, identity.project_id, tool_name, args, policy_version)
        
        row = ctx.approvals.create(
            agent_id=identity.agent_id,
            project_id=identity.project_id,
            tool=tool_name,
            arguments=args,
            reason=decision.reason,
            action_hash=ahash,
            execution_id=identity.execution_id,
        )
        
        ctx.event_bus.emit(
            type="approval_requested",
            source="guardrail_middleware",
            message=f"Approval requested for {tool_name}",
            payload={"approval_id": row.id, "action_hash": ahash}
        )
        
        status = await ctx.approvals.wait_for_resolution(row.id)
        
        current_hash = canonical_action_hash(identity.execution_id, identity.agent_id, identity.project_id, tool_name, args, policy_version)
        if current_hash != row.action_hash:
            ctx.event_bus.emit(type="approval_verification_failed", source="guardrail", message="Hash mismatch")
            raise GuardrailEnforcementError("Approval hash mismatch")
            
        if status == "APPROVED":
            # Atomically move from APPROVED -> CONSUMED. If this fails, another
            # consumer won the race and we must not execute the tool.
            transitioned = ctx.approvals.transition_status(row.id, "APPROVED", "CONSUMED")
            if not transitioned:
                ctx.event_bus.emit(type="approval_verification_failed", source="guardrail", message=f"Consume race lost {row.id}")
                raise GuardrailEnforcementError("Approval already consumed or invalid state")
            ctx.event_bus.emit(type="approval_consumed", source="guardrail", message=f"Consumed {row.id}")
            from aip.validation.evidence import append_guardrail_decision
            append_guardrail_decision(
                identity.execution_id,
                {
                    "source": "native_middleware",
                    "tool": tool_name,
                    "decision": "allow",
                    "reason": "approval_consumed",
                    "guardrail_id": decision.guardrail_id,
                },
            )
            return
            
        if status == "REJECTED":
            ctx.event_bus.emit(type="approval_rejected", source="guardrail", message=f"Rejected {row.id}")
            raise GuardrailEnforcementError(f"Action rejected by human reviewer")
            
        ctx.event_bus.emit(type="approval_expired", source="guardrail", message=f"Expired {row.id}")
        raise GuardrailEnforcementError(f"Approval wait expired for {tool_name}")

async def intercept_native_tool(tool_name: str, args: dict[str, Any], spec: AgentSpecification) -> None:
    """Enforce guardrails for native tools (called synchronously in _on_invoke mapping)."""
    await _audit_and_enforce(tool_name, args, spec)
