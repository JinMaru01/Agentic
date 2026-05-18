# ADR-003: FlowExecutor Interface — Decoupling flowconfig_service from flowManager

## Status
Accepted

## Date
2026-05-15

---

## Context

`flowconfig_service` (in `backend/flow/services/flowconfig_service.py`) directly instantiates and operates on `flowManager` (in `backend/flowcore/flowmanager.py`) in three methods. This creates five distinct coupling problems that make the service layer impossible to unit-test and unsafe to refactor:

### Problem 1 — Hard-coded instantiation in three places

```python
# getFlowConfig
fm = flowManager(flowid, versionid, 'flowv')

# saveversion
abc = flowManager(data['flowid'], data['version'], 'flowv')

# runTest
flowm = flowManager(flowid, versionid, 'flowv')
```

The service owns the creation of the engine. There is no way to inject a test double, mock, or alternative implementation.

### Problem 2 — Silent failure on construction

`flowManager.__init__` can fail silently when Redis has no entry for the flow:

```python
# flowmanager.py __init__
flowdetails = db.HGETALL(f"flow_id:{self.id}")
if not flowdetails:
    flowManager.loadFlowDetails(self.id)
    flowdetails = db.HGETALL(f"flow_id:{self.id}")
    if not flowdetails:
        return None   # ← __init__ returns None; object is in broken state
```

Python ignores `return None` in `__init__` — the object is returned to the caller anyway, but in a broken state (`compiledflow` never set). The service never checks for this. In `saveversion`, calling `abc.validateConfig(x)` after a failed init raises `AttributeError: 'flowManager' object has no attribute 'compiledflow'`.

### Problem 3 — Direct mutation of engine internal state

```python
# saveversion in flowconfig_service.py
abc.flowconfig["validflow"] = fvalid   # ← mutates flowManager's internal dict directly
```

The service bypasses all `flowManager` logic and writes directly into its `flowconfig` dict. This is invisible to the engine and breaks encapsulation completely.

### Problem 4 — Attribute coupling (reads internal fields directly)

```python
fm.validflow            # bool — is the flow graph valid?
fm.flow_design_status   # int — current design state
fm.owner_dep            # str — owning department
fm.flowconfig           # dict — full raw flow JSON (should be opaque to service)
```

Any rename or restructure of `flowManager` fields breaks the service. The service knows too much about the engine's internals.

### Problem 5 — State machine inconsistency discovered during evaluation

`flowconfig_service.stateiinfo` defines state labels as:
```python
{"1": "Design", "2": "Test", "3": "Verify", "4": "Publish", "5": "Production"}
```

But the actual `design_status` integers used in `nextState` DB queries are:
```
1 = Design  (redesign resets to 1)
2 = Test
3 = Verify
4 = Publish
5 = Production (live)
9 = Archived   (previous production demoted here)
99 = Rejected
```

The `stateiinfo` dict is missing `9` (Archived) and `99` (Rejected), and uses **string** keys (`"1"`) while DB queries use **integer** values (`dstatus+1`). The `stateiinfo[str(dstatus+1)]` call on line 160 will `KeyError` when `dstatus=4` → tries `"5"` (ok), `dstatus=5` → tries `"6"` (missing), `dstatus=9` → tries `"10"` (missing).

---

## Decision

Introduce a `FlowExecutor` Protocol in `backend/flowcore/protocols.py`. The service layer depends only on this Protocol. `flowManager` implements it. Tests use a `MockFlowExecutor`.

A factory function `get_flow_executor()` handles construction and raises explicitly on failure — replacing the three inline `flowManager(...)` calls.

---

## The Interface

### `backend/flowcore/protocols.py` (new file)

```python
from typing import Protocol, runtime_checkable


@runtime_checkable
class FlowExecutor(Protocol):
    """
    Contract between the service layer and the flow execution engine.
    flowManager implements this. Tests use MockFlowExecutor.
    """

    # --- Read-only state ---

    @property
    def validflow(self) -> bool:
        """True if the compiled flow graph passed validation."""
        ...

    @property
    def flow_design_status(self) -> int:
        """Current design_status integer from DB (1=Design, 2=Test, 3=Verify, 4=Publish, 5=Production, 9=Archived, 99=Rejected)."""
        ...

    @property
    def owner_dep(self) -> str:
        """Owning department ID as string."""
        ...

    # --- Config form operations ---

    def getConfigForm(self, ids: list, form_type: str) -> list:
        """Return form schema for all nodes (or specific ids) for the given form_type."""
        ...

    def validateConfig(self, data: dict) -> tuple[bool, str]:
        """Validate a single node's config. Returns (is_valid, message)."""
        ...

    def updateConfigJson(self, data: dict) -> None:
        """Write updated config for a node into the internal flow graph."""
        ...

    def setValidFlow(self, valid: bool) -> None:
        """
        Mark the flow as valid/invalid. Replaces direct mutation of flowconfig['validflow'].
        Implementation writes into self.flowconfig['validflow'].
        """
        ...

    def getFlowConfig(self) -> dict:
        """
        Return the serializable flow config dict (for DB persistence).
        Replaces direct access to flowManager.flowconfig.
        """
        ...

    # --- Execution ---

    def run(
        self,
        stack: list | None,
        mode: str,
        nodes: dict | None,
        fdata: dict | None,
    ) -> dict:
        """
        Execute the flow. mode: 'test' | 'production' | 'setting'.
        Returns {'stack': [...], 'nodes': {...}, 'data': [...]}.
        """
        ...
```

---

### `backend/flowcore/executor_factory.py` (new file)

```python
from flowcore.protocols import FlowExecutor
from flowcore.flowmanager import flowManager


class FlowNotFoundError(Exception):
    """Raised when a flow cannot be loaded from Redis or DB."""
    pass


def get_flow_executor(flowid: int, versionid: int, source: str = "flowv") -> FlowExecutor:
    """
    Factory for FlowExecutor. Raises FlowNotFoundError instead of returning
    a broken object when the flow does not exist.

    Args:
        flowid: The flow ID.
        versionid: The version ID.
        source: 'flowv' for a specific version, 'flow' for production version.

    Raises:
        FlowNotFoundError: If the flow cannot be found in Redis or DB.
    """
    fm = flowManager(flowid, versionid, source)
    if not hasattr(fm, "compiledflow") or fm.compiledflow is None:
        raise FlowNotFoundError(
            f"Flow {flowid} version {versionid} could not be loaded. "
            "Check Redis connectivity and that the flow exists in DB."
        )
    return fm
```

---

### Changes to `flowManager` — add two methods

Add to `backend/flowcore/flowmanager.py`:

```python
def setValidFlow(self, valid: bool) -> None:
    """Replace direct dict mutation: abc.flowconfig['validflow'] = fvalid"""
    self.flowconfig["validflow"] = valid

def getFlowConfig(self) -> dict:
    """Return the serializable flow config for DB persistence."""
    return self.flowconfig
```

These are the only two additions to `flowManager`. No existing methods change.

---

### Changes to `flowconfig_service` — use Protocol + factory

Replace all three `flowManager(...)` instantiations with `get_flow_executor(...)`:

**`getFlowConfig`** — before:
```python
fm = flowManager(flowid, versionid, 'flowv')
datafm = fm.getConfigForm([], 'runconfig')
rdata = {"validflow": fm.validflow, 'design_status': fm.flow_design_status, "data": datafm}
```
After:
```python
from flowcore.executor_factory import get_flow_executor, FlowNotFoundError

fm = get_flow_executor(flowid, versionid)
datafm = fm.getConfigForm([], 'runconfig')
rdata = {"validflow": fm.validflow, 'design_status': fm.flow_design_status, "data": datafm}
```

**`saveversion`** — before:
```python
abc = flowManager(data['flowid'], data['version'], 'flowv')
# ...
abc.flowconfig["validflow"] = fvalid   # ← direct mutation
stmt = (...).values(flow_json=abc.flowconfig, ...)
```
After:
```python
abc = get_flow_executor(data['flowid'], data['version'])
# ...
abc.setValidFlow(fvalid)               # ← method call
stmt = (...).values(flow_json=abc.getFlowConfig(), ...)
```

**`runTest`** — before:
```python
flowm = flowManager(flowid, versionid, 'flowv')
fdata = flowm.run(runstack.get('stack'), mode='test', ...)
audittrail.save("FlowConfig", flowm.owner_dep, data, user)
```
After:
```python
flowm = get_flow_executor(flowid, versionid)
fdata = flowm.run(runstack.get('stack'), mode='test', ...)
audittrail.save("FlowConfig", flowm.owner_dep, data, user)
```

---

### Fix `stateiinfo` — correct keys and values

Replace the broken dict in `flowconfig_service`:

```python
# BEFORE (wrong — string keys, missing states)
stateiinfo = {"1": "Design", "2": "Test", "3": "Verify", "4": "Publish", "5": "Production"}

# AFTER (correct — integer keys, all states present)
stateiinfo = {
    1: "Design",
    2: "Test",
    3: "Verify",
    4: "Publish",
    5: "Production",
    9: "Archived",
    99: "Rejected",
}
```

Update the two usages in `nextState` that call `flowconfig_service.stateiinfo[str(dstatus+1)]` → change to `flowconfig_service.stateiinfo[dstatus + 1]` (no `str()` cast).

---

## MockFlowExecutor for Tests

In `backend/app/tests/conftest.py` or a test fixture file:

```python
class MockFlowExecutor:
    """Test double for FlowExecutor. Inject into flowconfig_service tests."""

    def __init__(self, validflow=True, design_status=1, owner_dep="1", flowconfig=None):
        self._validflow = validflow
        self._design_status = design_status
        self._owner_dep = owner_dep
        self._flowconfig = flowconfig or {"nodeDataArray": [], "linkDataArray": [], "start": "1", "validflow": True}
        self._valid_set = None

    @property
    def validflow(self) -> bool:
        return self._validflow

    @property
    def flow_design_status(self) -> int:
        return self._design_status

    @property
    def owner_dep(self) -> str:
        return self._owner_dep

    def getConfigForm(self, ids, form_type):
        return []

    def validateConfig(self, data):
        return True, "Ok"

    def updateConfigJson(self, data):
        pass

    def setValidFlow(self, valid: bool):
        self._valid_set = valid
        self._flowconfig["validflow"] = valid

    def getFlowConfig(self) -> dict:
        return self._flowconfig

    def run(self, stack, mode, nodes, fdata):
        return {"stack": [], "nodes": None, "data": []}
```

---

## Consequences

### What this changes
- `flowconfig_service` no longer imports `flowManager` directly — imports `get_flow_executor` and `FlowNotFoundError` only
- `flowManager` gains 2 methods (`setValidFlow`, `getFlowConfig`) — all existing methods unchanged
- `FlowNotFoundError` replaces silent broken-object construction — callers get a clear exception
- `stateiinfo` corrected — `nextState` no longer risks `KeyError` on status 9 or 99
- Service methods are now unit-testable with `MockFlowExecutor` (no Redis, no DB required)

### What this does NOT change
- `flowManager` internal implementation — untouched beyond 2 added methods
- Redis key structure — unchanged
- API response shapes — unchanged
- `flowconfig.py` route handlers — unchanged (they call service, not engine)

### Risks
- `get_flow_executor` raises `FlowNotFoundError` where the old code silently created a broken object. The route handlers in `flowconfig.py` currently have bare `except Exception as e: raise e` — these will propagate `FlowNotFoundError` to the client as HTTP 500. Route handlers must be updated (ADR-001 scope: centralized error handling) to catch `FlowNotFoundError` and return HTTP 404.
- Coordinate with `tester`: write baseline tests for `getFlowConfig`, `saveversion`, `runTest` BEFORE implementing this change.

---

## Implementation Notes for Agents

**Assign to**: `flow-engineer` (new file `protocols.py` + `executor_factory.py` + 2 methods on `flowManager`), then `backend-dev` (update `flowconfig_service.py`)

**Sequence**:
1. `tester` — write baseline tests first (see ADR note above)
2. `flow-engineer` — create `backend/flowcore/protocols.py`
3. `flow-engineer` — create `backend/flowcore/executor_factory.py`
4. `flow-engineer` — add `setValidFlow()` and `getFlowConfig()` to `flowManager`
5. `backend-dev` — update `flowconfig_service`: replace 3 `flowManager(...)` calls, fix `stateiinfo`, remove direct `flowconfig` mutation
6. `tester` — run baseline tests, confirm all pass

**Do not** change `flowManager.__init__`, `run()`, `loadFlow()`, or any other existing method.
**Do not** add `FlowExecutor` as a base class to `flowManager` — `Protocol` works structurally (duck typing), no inheritance needed.
