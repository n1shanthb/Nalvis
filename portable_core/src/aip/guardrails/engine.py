"""Deterministic Guardrail Engine."""

from __future__ import annotations
from typing import Sequence

from aip.guardrails.models import Guardrail, GuardrailEffect
from aip.guardrails.decisions import PolicyRequest, PolicyDecision


class GuardrailEngine:
    """Evaluates PolicyRequests against a set of Guardrails deterministically."""
    
    def __init__(self, guardrails: Sequence[str | Guardrail]):
        # Filter out legacy string guardrails; only structured Guardrails are evaluated.
        self._rules = [g for g in guardrails if isinstance(g, Guardrail)]

    def evaluate(self, request: PolicyRequest) -> PolicyDecision:
        """Evaluate the request and return a definitive PolicyDecision."""
        matching_rules = [
            rule for rule in self._rules
            if rule.action == request.tool
        ]

        # Module 9: Deterministic condition evaluation
        active_rules = []
        for rule in matching_rules:
            if not rule.conditions:
                active_rules.append(rule)
                continue
            
            # Evaluate explicit condition fields
            matched = True
            
            # 1. match_context
            if rule.conditions.match_context:
                for k, v in rule.conditions.match_context.items():
                    if request.context.get(k) != v:
                        matched = False
                        break
            
            # 2. match_arguments
            if matched and rule.conditions.match_arguments:
                for k, v in rule.conditions.match_arguments.items():
                    if request.arguments.get(k) != v:
                        matched = False
                        break
                        
            # 3. match_arguments_in
            if matched and rule.conditions.match_arguments_in:
                for k, allowed_values in rule.conditions.match_arguments_in.items():
                    val = request.arguments.get(k)
                    if val not in allowed_values:
                        matched = False
                        break
            
            if matched:
                active_rules.append(rule)

        if not active_rules:
            return PolicyDecision(
                decision=GuardrailEffect.ALLOW,
                reason="No matching guardrail rules for this action."
            )

        # Precedence: DENY > REQUIRE_APPROVAL > ALLOW
        require_approval_rule = None

        for rule in active_rules:
            if rule.effect == GuardrailEffect.DENY:
                return PolicyDecision(
                    decision=GuardrailEffect.DENY,
                    guardrail_id=rule.id,
                    reason=f"Action denied by rule '{rule.id}'."
                )
            if rule.effect == GuardrailEffect.REQUIRE_APPROVAL:
                if not require_approval_rule:
                    require_approval_rule = rule

        if require_approval_rule:
            return PolicyDecision(
                decision=GuardrailEffect.REQUIRE_APPROVAL,
                guardrail_id=require_approval_rule.id,
                reason=f"Action requires approval due to rule '{require_approval_rule.id}'."
            )

        allow_rule = active_rules[0]
        return PolicyDecision(
            decision=GuardrailEffect.ALLOW,
            guardrail_id=allow_rule.id,
            reason=f"Action allowed by rule '{allow_rule.id}'."
        )
