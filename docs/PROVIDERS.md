# Provider Setups

This document shows practical `profiles.yaml` patterns for common setups.

## 1. Single OpenAI Profile For All Roles

This is the fastest way to get TriadLLM running.

```yaml
default_profile: openai_default

profiles:
  openai_default:
    label: OpenAI Default
    provider: openai
    base_url: https://api.openai.com/v1
    model: gpt-4.1-mini
    api_key_env: OPENAI_API_KEY
    temperature: 0.2
```

With this configuration, all three roles fall back to `openai_default`.

## 2. Mixed Providers By Role

```yaml
default_profile: orchestrator_mistral_medium_latest

profiles:
  orchestrator_mistral_medium_latest:
    label: Mistral Medium Latest
    provider: mistral
    base_url: https://api.mistral.ai/v1
    model: mistral-medium-latest
    api_key_env: MISTRAL_API_KEY
    temperature: 0.7

  processor_magistral_medium_latest:
    label: Magistral Medium Latest
    provider: mistral
    base_url: https://api.mistral.ai/v1
    model: magistral-medium-latest
    api_key_env: MISTRAL_API_KEY
    temperature: 0.7

  validator_gpt54_medium:
    label: GPT-5.4 Medium
    provider: openai
    base_url: https://api.openai.com/v1
    model: gpt-5.4
    api_key_env: OPENAI_API_KEY
    temperature: 1.0
    reasoning_effort: medium
    reasoning_summary: auto
```

Then assign them at runtime:

```text
/model set orchestrator orchestrator_mistral_medium_latest
/model set processor processor_magistral_medium_latest
/model set validator validator_gpt54_medium
```

## 3. Local OpenAI-Compatible Model

```yaml
default_profile: local_glm47_flash

profiles:
  local_glm47_flash:
    label: Local GLM-4.7 Flash
    provider: openai_compatible
    base_url: http://127.0.0.1:8080/v1
    model: zai-org/GLM-4.7-Flash
    api_key_literal: dummy
    temperature: 0.7
    timeout: 60
```

This uses the official OpenAI SDK pointed at your local endpoint.

## 4. One Provider Family, Different Models

```yaml
default_profile: orchestrator_openai

profiles:
  orchestrator_openai:
    label: OpenAI Orchestrator
    provider: openai
    base_url: https://api.openai.com/v1
    model: gpt-4.1-mini
    api_key_env: OPENAI_API_KEY
    temperature: 0.2

  processor_openai:
    label: OpenAI Processor
    provider: openai
    base_url: https://api.openai.com/v1
    model: gpt-5.4
    api_key_env: OPENAI_API_KEY
    temperature: 1.0
    reasoning_effort: medium
    reasoning_summary: auto

  validator_openai:
    label: OpenAI Validator
    provider: openai
    base_url: https://api.openai.com/v1
    model: gpt-5.4
    api_key_env: OPENAI_API_KEY
    temperature: 1.0
    reasoning_effort: medium
    reasoning_summary: auto
```

## Notes

- Provider availability depends on your account.
- A model alias shown in docs may not exist in your tenant.
- The runtime supports any supported provider family in any role.
- If a profile id exists but is not assigned to a role, it will not be used unless selected with `/model set ...`.
