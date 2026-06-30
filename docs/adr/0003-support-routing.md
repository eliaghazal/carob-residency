# ADR 0003: Support routing with a model and a rules fallback

Date: 2026-03-03 · Status: accepted · Author: Karim Nassar

## Context

Agents spent the first minutes of each conversation moving it to the right queue. Messages arrive
in English and in Arabic, often in dialect.

## Decision

- Route the first message of a conversation to a queue with a classifier over the 77 BANKING77
  intents, trained on BANKING77 (English) and ArBanking77 (Arabic) by `src/carob_ml`.
- Models live in a registry directory with a manifest (version, SHA-256, intent-to-queue map,
  metrics, data manifest hash).
- Keep keyword rules as the fallback when no model is deployed or loading fails.
- Below a confidence threshold, send the conversation to triage rather than guess.

## Consequences

Routing quality depends on the training data's language varieties; report metrics by variety, not
only overall. Changing the model is a deploy, with a version in every conversation row.
