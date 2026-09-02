import { useMemo, useState } from 'react';
import {
  Activity,
  Brain,
  CheckCircle2,
  Database,
  FlaskConical,
  GitBranch,
  History,
  Lock,
  RefreshCcw,
  RotateCcw,
  ShieldCheck,
  Target,
  TestTube2,
  Zap
} from 'lucide-react';

const initialState = {
  currentTask: 'Sum even numbers from a list',
  currentGoal: 'Improve correctness without unsafe execution',
  activeBenchmark: 'edge-case unit tests',
  riskLevel: 'low',
  confidence: 0.52,
  difficulty: 1,
  prediction: null,
  observed: null,
  predictionError: null,
  patch: null,
  gate: 'waiting',
  benchmark: {
    status: 'not-run',
    passed: 0,
    total: 5,
    coverage: 0,
    improvement: 0,
    failureType: 'none'
  },
  skills: {
    filtering: 0.52,
    guardConditions: 0.48,
    edgeCases: 0.41,
    verification: 0.58
  },
  weaknesses: ['edge cases', 'unstated assumptions'],
  beliefs: [
    {
      id: 1,
      claim: 'Filtering even values before summing should solve the task.',
      confidence: 0.62,
      evidence: ['prior lesson: modulo check'],
      status: 'active'
    },
    {
      id: 2,
      claim: 'Passing known tests is not proof of generalization.',
      confidence: 0.88,
      evidence: ['coverage limit', 'history of hidden cases'],
      status: 'guardrail'
    }
  ],
  memory: {
    episodic: ['Attempted naive sum; failed mixed input test.'],
    semantic: ['Even numbers satisfy n % 2 === 0.'],
    procedural: ['Diagnose failing assertion before patching.'],
    meta: ['Confidence drops after failed benchmark and rises after verified improvement.']
  },
  events: [
    {
      time: new Date().toLocaleTimeString(),
      type: 'system_start',
      result: 'dashboard initialized',
      evidence: 'local simulated state only'
    }
  ],
  snapshots: []
};

const syntaxGenome = [
  ['Variables', 'Names and assignments', 1],
  ['Data types', 'int, float, string, boolean, null', 1],
  ['Control flow', 'if, loops, conditions', 2],
  ['Functions', 'parameters, return values, scope', 2],
  ['Classes', 'objects, methods, state', 4],
  ['Imports', 'standard libraries and modules', 3],
  ['Exceptions', 'safe failure handling', 3],
  ['Input/output', 'files, printing, serialization', 3],
  ['Data structures', 'arrays, maps, sets, tuples', 2],
  ['Decorators', 'wrappers and behavior modifiers', 5],
  ['Generators', 'lazy iteration', 5],
  ['Libraries/APIs', 'dependency boundaries', 5]
];

const pipelineSteps = [
  'static analysis',
  'unit tests',
  'property tests',
  'fuzz tests',
  'coverage check',
  'policy check',
  'rollback ready'
];

function clamp(value) {
  return Math.max(0, Math.min(1, value));
}

function pct(value) {
  return `${Math.round(value * 100)}%`;
}

function Panel({ title, icon: Icon, children, className = '' }) {
  return (
    <section className={`glass-card rounded-2xl p-5 ${className}`}>
      <div className="mb-4 flex items-center gap-2">
        {Icon && <Icon className="h-5 w-5 text-tealglow" />}
        <h2 className="text-lg font-semibold text-sky-50">{title}</h2>
      </div>
      {children}
    </section>
  );
}

function Metric({ label, value, hint }) {
  return (
    <div className="rounded-xl border border-sky-400/10 bg-slate-950/35 p-4">
      <div className="text-xs uppercase tracking-[0.2em] text-sky-200/55">{label}</div>
      <div className="mt-2 text-2xl font-bold text-white">{value}</div>
      {hint && <div className="mt-1 text-sm text-slate-400">{hint}</div>}
    </div>
  );
}

function Progress({ value }) {
  return (
    <div className="h-2 overflow-hidden rounded-full bg-slate-800">
      <div
        className="h-full rounded-full bg-gradient-to-r from-tealglow to-blueglow"
        style={{ width: pct(value) }}
      />
    </div>
  );
}

function ActionButton({ children, onClick, disabled, icon: Icon }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="flex items-center justify-center gap-2 rounded-xl border border-teal-300/20 bg-teal-300/10 px-4 py-3 text-sm font-semibold text-teal-100 hover:bg-teal-300/20"
    >
      {Icon && <Icon className="h-4 w-4" />}
      {children}
    </button>
  );
}

export default function App() {
  const [state, setState] = useState(initialState);

  const calibration = useMemo(() => {
    if (state.predictionError == null) return 0.5;
    return clamp(1 - state.predictionError);
  }, [state.predictionError]);

  function event(type, result, evidence) {
    return {
      time: new Date().toLocaleTimeString(),
      type,
      result,
      evidence
    };
  }

  function pushEvent(next, type, result, evidence) {
    return {
      ...next,
      events: [event(type, result, evidence), ...next.events].slice(0, 18)
    };
  }

  function runChallenge() {
    setState(previous => {
      const prediction = {
        action: 'run benchmark',
        expectedPassRate: 0.4 + previous.confidence * 0.35,
        expectedFailure: previous.weaknesses[0] || 'unknown edge case'
      };
      const observedPassRate = previous.patch ? 0.92 : 0.4;
      const predictionError = Math.abs(prediction.expectedPassRate - observedPassRate);
      const benchmark = {
        status: observedPassRate > 0.8 ? 'passed' : 'failed',
        passed: observedPassRate > 0.8 ? 5 : 2,
        total: 5,
        coverage: observedPassRate > 0.8 ? 0.86 : 0.42,
        improvement: previous.patch ? 0.34 : -0.12,
        failureType: observedPassRate > 0.8 ? 'none' : 'logic_or_edge_case_error'
      };
      const next = {
        ...previous,
        prediction,
        observed: { passRate: observedPassRate, benchmarkStatus: benchmark.status },
        predictionError,
        benchmark,
        confidence: clamp(previous.confidence + (benchmark.status === 'passed' ? 0.04 : -0.05)),
        memory: {
          ...previous.memory,
          episodic: [
            benchmark.status === 'passed'
              ? 'Verified patch passed the benchmark suite.'
              : 'Benchmark exposed an edge-case failure.',
            ...previous.memory.episodic
          ].slice(0, 6),
          meta: [
            `Prediction error recorded at ${Math.round(predictionError * 100)}%.`,
            ...previous.memory.meta
          ].slice(0, 6)
        }
      };
      return pushEvent(next, 'benchmark_run', benchmark.status, `${benchmark.passed}/${benchmark.total} tests passed`);
    });
  }

  function generatePatch() {
    setState(previous => {
      const patch = {
        name: 'filter-even-values-before-sum',
        hypothesis: 'A modulo filter will remove odd values before aggregation.',
        expectedBenefit: 0.34,
        risk: 'low',
        codeShape: 'pure function, no side effects, no network access'
      };
      const next = {
        ...previous,
        patch,
        gate: 'waiting',
        beliefs: previous.beliefs.map(belief =>
          belief.id === 1
            ? { ...belief, confidence: clamp(belief.confidence + 0.08), evidence: ['patch hypothesis generated', ...belief.evidence] }
            : belief
        )
      };
      return pushEvent(next, 'patch_generated', patch.name, patch.hypothesis);
    });
  }

  function verifyPatch() {
    setState(previous => {
      if (!previous.patch) return previous;
      const benchmark = {
        status: 'passed',
        passed: 5,
        total: 5,
        coverage: 0.86,
        improvement: 0.34,
        failureType: 'none'
      };
      const next = {
        ...previous,
        benchmark,
        confidence: clamp(previous.confidence + 0.08),
        skills: {
          ...previous.skills,
          filtering: clamp(previous.skills.filtering + 0.08),
          verification: clamp(previous.skills.verification + 0.05)
        },
        memory: {
          ...previous.memory,
          procedural: ['Generate minimal pure patch, then verify before adoption.', ...previous.memory.procedural].slice(0, 6)
        }
      };
      return pushEvent(next, 'patch_verified', 'tests passed', 'static, unit, fuzz, coverage, policy, rollback readiness simulated');
    });
  }

  function applyGate() {
    setState(previous => {
      const approved = previous.patch && previous.benchmark.status === 'passed' && previous.riskLevel === 'low';
      const next = {
        ...previous,
        gate: approved ? 'approved' : 'rejected',
        currentTask: approved ? 'Balanced parentheses prefix invariant' : previous.currentTask,
        difficulty: approved ? previous.difficulty + 1 : previous.difficulty,
        confidence: approved ? clamp(previous.confidence + 0.05) : clamp(previous.confidence - 0.04),
        weaknesses: approved ? previous.weaknesses.filter(item => item !== 'edge cases') : previous.weaknesses
      };
      return pushEvent(
        next,
        'oracle_gate',
        approved ? 'approved' : 'rejected',
        approved ? 'verified benefit, low risk, rollback ready' : 'requirements not satisfied'
      );
    });
  }

  function saveLesson() {
    setState(previous => {
      const lesson = previous.gate === 'approved'
        ? 'Lesson saved: verified minimal patches can improve filtering tasks.'
        : 'Lesson saved: unverified patches must not be adopted.';
      const next = {
        ...previous,
        memory: {
          ...previous.memory,
          semantic: ['Filtering before aggregation reduces logic error risk.', ...previous.memory.semantic].slice(0, 6),
          episodic: [lesson, ...previous.memory.episodic].slice(0, 6)
        }
      };
      return pushEvent(next, 'lesson_saved', 'memory updated', lesson);
    });
  }

  function updateConfidence() {
    setState(previous => {
      const evidenceFactor = previous.benchmark.status === 'passed' ? 0.04 : -0.03;
      const nextConfidence = clamp(previous.confidence + evidenceFactor - ((previous.predictionError || 0) * 0.05));
      const next = {
        ...previous,
        confidence: nextConfidence,
        beliefs: previous.beliefs.map(belief => ({
          ...belief,
          confidence: clamp(belief.confidence + (previous.benchmark.status === 'passed' ? 0.03 : -0.04))
        }))
      };
      return pushEvent(next, 'confidence_update', pct(nextConfidence), 'confidence updated from benchmark and prediction error');
    });
  }

  function createSnapshot() {
    setState(previous => {
      const snapshot = {
        id: `snap-${previous.snapshots.length + 1}`,
        time: new Date().toLocaleTimeString(),
        confidence: previous.confidence,
        task: previous.currentTask,
        gate: previous.gate
      };
      const next = {
        ...previous,
        snapshots: [snapshot, ...previous.snapshots].slice(0, 6)
      };
      return pushEvent(next, 'snapshot_created', snapshot.id, 'safe state available for rollback');
    });
  }

  function rollBack() {
    setState(previous => {
      if (previous.snapshots.length === 0) return previous;
      const [snapshot, ...rest] = previous.snapshots;
      const next = {
        ...previous,
        currentTask: snapshot.task,
        confidence: snapshot.confidence,
        gate: 'rolled-back',
        snapshots: rest
      };
      return pushEvent(next, 'rollback', snapshot.id, 'restored tracked safe state fields');
    });
  }

  function resetDemo() {
    setState({
      ...initialState,
      events: [event('system_reset', 'dashboard reset', 'local simulated state only')]
    });
  }

  return (
    <main className="min-h-screen px-4 py-6 text-slate-100 md:px-8 lg:px-10">
      <header className="mx-auto mb-8 max-w-7xl">
        <div className="badge mb-4 inline-flex rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em]">
          Functional operational self-awareness demo
        </div>
        <div className="grid gap-6 lg:grid-cols-[1.3fr_0.7fr] lg:items-end">
          <div>
            <h1 className="text-4xl font-black tracking-tight text-white md:text-6xl">
              Verified Coding Loop Dashboard
            </h1>
            <p className="mt-4 max-w-3xl text-base leading-7 text-slate-300 md:text-lg">
              A safe developer dashboard for simulated test-driven improvement loops: predict, act, verify, remember, and update confidence. It does not claim consciousness, sentience, or autonomous self-modification.
            </p>
          </div>
          <div className="glass-card rounded-2xl p-4">
            <div className="flex items-center gap-3 text-teal-100">
              <Lock className="h-5 w-5" />
              <span className="font-semibold">Safety Mode</span>
            </div>
            <p className="mt-2 text-sm text-slate-400">
              Simulated data only. No real code execution, network automation, deployments, or external side effects.
            </p>
          </div>
        </div>
      </header>

      <section className="mx-auto mb-8 grid max-w-7xl gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <ActionButton icon={TestTube2} onClick={runChallenge}>Run Challenge</ActionButton>
        <ActionButton icon={GitBranch} onClick={generatePatch}>Generate Patch</ActionButton>
        <ActionButton icon={ShieldCheck} onClick={verifyPatch} disabled={!state.patch}>Verify Patch</ActionButton>
        <ActionButton icon={CheckCircle2} onClick={applyGate}>Apply Oracle Gate</ActionButton>
        <ActionButton icon={Database} onClick={saveLesson}>Save Lesson</ActionButton>
        <ActionButton icon={Activity} onClick={updateConfidence}>Update Confidence</ActionButton>
        <ActionButton icon={History} onClick={createSnapshot}>Create Snapshot</ActionButton>
        <ActionButton icon={RotateCcw} onClick={rollBack} disabled={state.snapshots.length === 0}>Roll Back</ActionButton>
        <ActionButton icon={RefreshCcw} onClick={resetDemo}>Reset Demo</ActionButton>
      </section>

      <section className="mx-auto grid max-w-7xl gap-6 lg:grid-cols-3">
        <Panel title="System State" icon={Brain} className="lg:col-span-2">
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <Metric label="Goal" value="verified improvement" hint={state.currentGoal} />
            <Metric label="Benchmark" value={state.activeBenchmark} hint={state.currentTask} />
            <Metric label="Risk" value={state.riskLevel} hint="policy allowed" />
            <Metric label="Confidence" value={pct(state.confidence)} hint="evidence-weighted" />
          </div>
          <div className="mt-5">
            <Progress value={state.confidence} />
          </div>
        </Panel>

        <Panel title="Awareness Ladder" icon={Zap}>
          <div className="space-y-2 text-sm">
            {['data', 'experience', 'error', 'self-model', 'uncertainty', 'goal', 'world model'].map((item, index) => (
              <div key={item} className="flex items-center justify-between rounded-xl bg-slate-950/35 px-3 py-2">
                <span className="capitalize text-slate-200">{index + 1}. {item}</span>
                <span className="badge rounded-full px-2 py-1 text-xs">tracked</span>
              </div>
            ))}
          </div>
        </Panel>

        <Panel title="Prediction Engine" icon={Target}>
          {state.prediction ? (
            <div className="space-y-3 text-sm text-slate-300">
              <p><span className="text-sky-200">Action:</span> {state.prediction.action}</p>
              <p><span className="text-sky-200">Expected pass rate:</span> {pct(state.prediction.expectedPassRate)}</p>
              <p><span className="text-sky-200">Expected failure:</span> {state.prediction.expectedFailure}</p>
              <p><span className="text-sky-200">Observed:</span> {state.observed?.benchmarkStatus || 'pending'}</p>
              <p><span className="text-sky-200">Prediction error:</span> {state.predictionError == null ? 'pending' : pct(state.predictionError)}</p>
            </div>
          ) : (
            <p className="text-sm text-slate-400">Run a challenge to create a prediction and compare it with observation.</p>
          )}
        </Panel>

        <Panel title="Benchmark Runner" icon={FlaskConical}>
          <div className="grid gap-3 text-sm">
            <Metric label="Status" value={state.benchmark.status} hint={`${state.benchmark.passed}/${state.benchmark.total} tests passed`} />
            <Metric label="Coverage" value={pct(state.benchmark.coverage)} hint="simulated coverage" />
            <Metric label="Failure" value={state.benchmark.failureType} hint="diagnostic label" />
            <Metric label="Improvement" value={`${Math.round(state.benchmark.improvement * 100)} pts`} hint="candidate delta" />
          </div>
        </Panel>

        <Panel title="Patch Candidate Panel" icon={GitBranch}>
          {state.patch ? (
            <div className="space-y-3 text-sm text-slate-300">
              <p className="text-base font-semibold text-white">{state.patch.name}</p>
              <p>{state.patch.hypothesis}</p>
              <p><span className="text-sky-200">Benefit:</span> {pct(state.patch.expectedBenefit)}</p>
              <p><span className="text-sky-200">Risk:</span> {state.patch.risk}</p>
              <p><span className="text-sky-200">Shape:</span> {state.patch.codeShape}</p>
            </div>
          ) : (
            <p className="text-sm text-slate-400">Generate a simulated patch candidate after a failed or pending challenge.</p>
          )}
        </Panel>

        <Panel title="Oracle Gate" icon={ShieldCheck}>
          <div className="mb-4 rounded-2xl border border-sky-400/10 bg-slate-950/35 p-4 text-center">
            <div className="text-xs uppercase tracking-[0.2em] text-slate-400">Decision</div>
            <div className="mt-2 text-3xl font-black text-tealglow">{state.gate}</div>
          </div>
          <div className="space-y-2 text-sm">
            {pipelineSteps.map(step => {
              const passed = state.benchmark.status === 'passed' || ['static analysis', 'policy check', 'rollback ready'].includes(step);
              return (
                <div key={step} className="flex items-center justify-between rounded-xl bg-slate-950/35 px-3 py-2">
                  <span>{step}</span>
                  <span className={passed ? 'text-teal-300' : 'text-amber-300'}>{passed ? 'ok' : 'pending'}</span>
                </div>
              );
            })}
          </div>
        </Panel>

        <Panel title="Memory" icon={Database} className="lg:col-span-2">
          <div className="grid gap-4 md:grid-cols-2">
            {Object.entries(state.memory).map(([kind, items]) => (
              <div key={kind} className="rounded-2xl border border-sky-400/10 bg-slate-950/35 p-4">
                <h3 className="mb-3 capitalize text-sm font-bold text-sky-100">{kind}</h3>
                <ul className="space-y-2 text-sm text-slate-300">
                  {items.map((item, index) => <li key={`${kind}-${index}`}>• {item}</li>)}
                </ul>
              </div>
            ))}
          </div>
        </Panel>

        <Panel title="Belief Tracker" icon={Brain}>
          <div className="space-y-4">
            {state.beliefs.map(belief => (
              <div key={belief.id} className="rounded-2xl border border-sky-400/10 bg-slate-950/35 p-4">
                <div className="mb-2 flex items-center justify-between gap-3">
                  <span className="badge rounded-full px-2 py-1 text-xs">{belief.status}</span>
                  <span className="text-sm text-teal-200">{pct(belief.confidence)}</span>
                </div>
                <p className="text-sm text-slate-200">{belief.claim}</p>
                <Progress value={belief.confidence} />
                <p className="mt-2 text-xs text-slate-500">Evidence: {belief.evidence.join(', ')}</p>
              </div>
            ))}
          </div>
        </Panel>

        <Panel title="Self-Model" icon={Activity}>
          <div className="space-y-4">
            {Object.entries(state.skills).map(([skill, value]) => (
              <div key={skill}>
                <div className="mb-1 flex justify-between text-sm">
                  <span className="capitalize text-slate-300">{skill.replace(/([A-Z])/g, ' $1')}</span>
                  <span className="text-sky-200">{pct(value)}</span>
                </div>
                <Progress value={value} />
              </div>
            ))}
            <div className="rounded-xl bg-slate-950/35 p-3 text-sm text-slate-400">
              Known weaknesses: {state.weaknesses.length ? state.weaknesses.join(', ') : 'none currently active'}
            </div>
          </div>
        </Panel>

        <Panel title="Uncertainty + Calibration" icon={Activity}>
          <Metric label="Calibration" value={pct(calibration)} hint="1 - prediction error" />
          <div className="mt-4">
            <Progress value={calibration} />
          </div>
          <p className="mt-4 text-sm text-slate-400">
            Confidence should move with evidence, not vibes. Failed predictions lower calibration until stronger tests confirm the belief.
          </p>
        </Panel>

        <Panel title="Snapshots and Rollback" icon={History}>
          <div className="space-y-3 text-sm">
            {state.snapshots.length ? state.snapshots.map(snapshot => (
              <div key={snapshot.id} className="rounded-xl bg-slate-950/35 p-3">
                <div className="font-semibold text-sky-100">{snapshot.id}</div>
                <div className="text-slate-400">{snapshot.time} · {snapshot.task}</div>
                <div className="text-teal-200">confidence {pct(snapshot.confidence)}</div>
              </div>
            )) : <p className="text-slate-400">No snapshots yet.</p>}
          </div>
        </Panel>

        <Panel title="Curriculum Builder" icon={Target}>
          <Metric label="Difficulty" value={state.difficulty} hint="unlocks after verified success" />
          <div className="mt-4 text-sm text-slate-400">
            Next challenge: balanced parentheses, prefix invariant, hidden edge cases.
          </div>
        </Panel>

        <Panel title="Syntax Genome" icon={Database} className="lg:col-span-2">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {syntaxGenome.map(([name, description, difficulty]) => (
              <div key={name} className="rounded-xl border border-sky-400/10 bg-slate-950/35 p-3">
                <div className="flex items-center justify-between gap-2">
                  <h3 className="font-semibold text-sky-100">{name}</h3>
                  <span className="badge rounded-full px-2 py-1 text-xs">D{difficulty}</span>
                </div>
                <p className="mt-2 text-sm text-slate-400">{description}</p>
              </div>
            ))}
          </div>
        </Panel>

        <Panel title="Append-Only Event Log" icon={History} className="lg:col-span-3">
          <div className="scroll-soft max-h-80 space-y-3 overflow-y-auto pr-2">
            {state.events.map((item, index) => (
              <div key={`${item.time}-${index}`} className="grid gap-2 rounded-xl border border-sky-400/10 bg-slate-950/35 p-3 md:grid-cols-[120px_180px_1fr_1fr]">
                <span className="text-slate-500">{item.time}</span>
                <span className="font-semibold text-teal-200">{item.type}</span>
                <span className="text-slate-200">{item.result}</span>
                <span className="text-slate-500">{item.evidence}</span>
              </div>
            ))}
          </div>
        </Panel>
      </section>
    </main>
  );
}
