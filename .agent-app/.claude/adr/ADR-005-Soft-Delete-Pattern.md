# ADR-005: Soft-Delete Pattern for Portfolio and Other Entities

## Status
Proposed

## Context
The current portfolio implementation uses a `is_active` boolean field to implement soft-delete semantics. This pattern is consistent with other domains like `flow` and `customer360` that also use soft-delete. However, this pattern has not been formally documented as a project-wide architectural decision, leading to inconsistent implementation across domains and potential confusion during onboarding.

## Decision
Adopt `is_active` soft-delete pattern as the standard for all entities in the system. All new and existing models must include an `is_active` boolean column with default `True`, and all queries must filter by `is_active == True` unless explicitly retrieving deleted records.

## Consequences
- **Changes**: All service methods must include `is_active == True` in their query filters. All new models must include `is_active` column.
- **Does not change**: Hard-delete operations are not allowed; all deletions are soft.
- **Risks**: Developers may forget to filter by `is_active` in new queries, leading to data leakage. Requires enforcement via code reviews and automated checks.

## Implementation Notes
- All models must include: `is_active = Column(Boolean, default=True)`
- All service methods must filter queries: `query(...).filter(is_active == True)`
- All API responses must include `is_active` field in response models
- All database migrations must preserve `is_active` column
- All new entities must follow this pattern by default
- Document this pattern in `ARCHITECTURE.md` and `CONVENTIONS.md`
- Add automated check to CI pipeline to verify `is_active` column exists in all models
