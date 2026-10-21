"""Reproduce the deck's numbers directly from the saved KEV responses."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from harness.score import score

MODELS = [('kev-0.8b', '20261014'), ('kev-4b', '20261015'),
          ('kev-9b', '20261015'), ('kev-27b', '20261015')]


def close(a, b):
    if isinstance(a, dict):
        return isinstance(b, dict) and a.keys() == b.keys() and all(close(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return isinstance(b, list) and len(a) == len(b) and all(close(x, y) for x, y in zip(a, b))
    if isinstance(a, float):
        return isinstance(b, (int, float)) and math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12)
    return a == b


def analyse():
    qpath = ROOT / 'data/questions/dataset_v1.jsonl'
    allq = [json.loads(l) for l in qpath.read_text().splitlines()]
    test = [q for q in allq if q['split'] == 'test']
    byid = {q['question_id']: q for q in allq}
    basic = [q for q in test if q['request'] == 'basic']
    reasons = [q for q in test if q['request'] == 'reason']
    assert len(allq) == 348 and len(test) == 281
    assert sum(len(q['questions']) for q in test) == 725
    bases = {split: {q['base_design_id'] for q in allq if q['split'] == split}
             for split in ['test', 'dev']}
    assert not bases['test'].intersection(bases['dev'])
    # The tool flow never rejects a design in vlog and then synthesizes it.
    assert not any(not q['correct_answer']['compiles'] and q['correct_answer']['synthesizes'] for q in basic)
    out = {
        'dataset_sha256': hashlib.sha256(qpath.read_bytes()).hexdigest(),
        'test_request_counts': dict(Counter(q['request'] for q in test)),
        'test_truth_counts': {k: dict(Counter(str(q['correct_answer'][k]) for q in test if k in q['questions']))
                              for k in sorted({k for q in test for k in q['questions']})},
        'test_reason_counts': dict(Counter(q['correct_answer']['reason'] for q in reasons)),
        'groups': {}, 'models': {},
    }
    # The ten options of the failure-reason question, and how often each one is the correct answer.
    all_reasons = [q for q in allq if q['request'] == 'reason']
    options = all_reasons[0]['questions']['reason']['criteria']
    assert all(q['questions']['reason']['criteria'] == options for q in all_reasons)
    assert all(q['evidence']['classes'] == [q['correct_answer']['reason']] for q in all_reasons)
    out['reason_options'] = options
    out['reason_counts_by_split'] = {split: dict(Counter(q['correct_answer']['reason'] for q in all_reasons if q['split'] == split))
                                     for split in ['test', 'dev']}
    out['reason_injected_edits'] = sum(q['evidence'].get('edit') is not None for q in all_reasons)
    reason_ids = {q['design_id'] for q in all_reasons}
    no_reason = [q for q in allq if q['request'] == 'basic' and not q['correct_answer']['synthesizes'] and q['design_id'] not in reason_ids]
    out['synthesis_failures_without_reason'] = {
        'n': len(no_reason), 'splits': dict(Counter(q['split'] for q in no_reason)),
        'classes': dict(Counter(c for q in no_reason for c in q['evidence']['classes'])),
        'compile_fails': sum(not q['correct_answer']['compiles'] for q in no_reason)}
    for group in sorted({q['group'] for q in allq}):
        ab = [q for q in allq if q['group'] == group and q['request'] == 'basic']
        tb = [q for q in basic if q['group'] == group]
        out['groups'][group] = {'all_designs': len(ab), 'test_designs': len(tb),
                                'test_synthesis_failures': sum(not q['correct_answer']['synthesizes'] for q in tb)}
    for model, stamp in MODELS:
        folder = ROOT / 'results/kev' / f'dataset_v1_{model}_{stamp}'
        answerpath = folder / f'dataset_v1__{model}.jsonl'
        rows = [json.loads(l) for l in answerpath.read_text().splitlines()]
        answers = {r['question_id']: r for r in rows}
        assert len(rows) == len(answers) == len(allq)
        assert set(answers) == set(byid)
        assert all(a.get('status') == 200 and not a.get('error') for a in rows)
        assert all(set(a['response']['answers']) == set(byid[a['question_id']]['questions']) for a in rows)
        saved = json.loads(Path(str(answerpath) + '.score.json').read_text())
        table, missing = score(qpath, 'kev', split='test', answers_file=answerpath)
        assert missing == saved['missing'] == 0 and close(table, saved['table'])
        assert sum(t['unscored'] for t in table) == 0
        manifest = json.loads((folder / 'manifest.json').read_text())
        assert out['dataset_sha256'] == manifest['dataset_sha256']
        data = {'table': {t['key']: t for t in table}, 'manifest': manifest,
                'answers_file': str(answerpath.relative_to(ROOT)),
                'answers_sha256': hashlib.sha256(answerpath.read_bytes()).hexdigest(),
                'binary': {}, 'reason_by_class': {}, 'pair_counts': {}}
        data['noul'] = {}
        for key in ['compiles', 'synthesizes']:
            counts = Counter()
            probs = {'pass': [], 'fail': []}
            for q in basic:
                p = answers[q['question_id']]['response']['answers'][key]['noul']
                counts[(q['correct_answer'][key], p >= 0.5)] += 1
                probs['pass' if q['correct_answer'][key] else 'fail'].append([q['question_id'], p])
            tp, fn, tn, fp = [counts[k] for k in [(True, True), (True, False), (False, False), (False, True)]]
            data['binary'][key] = dict(pass_correct=tp, pass_wrong=fn, fail_correct=tn, fail_wrong=fp,
                                        n_pass=tp + fn, n_fail=tn + fp,
                                        pass_rate=tp / (tp + fn), fail_rate=tn / (tn + fp),
                                        yes_answers=tp + fp)
            data['noul'][key] = probs
        # A "does not compile" answer together with a "synthesizes" answer for the same design.
        data['no_compile_but_synthesizes'] = sum(
            answers[q['question_id']]['response']['answers']['compiles']['noul'] < 0.5 <=
            answers[q['question_id']]['response']['answers']['synthesizes']['noul'] for q in basic)
        data['synthesis_failure_subsets'] = {}
        successes = [answers[q['question_id']]['response']['answers']['synthesizes']['noul']
                     for q in basic if q['correct_answer']['synthesizes']]
        for compiles in [True, False]:
            subset = [q for q in basic if not q['correct_answer']['synthesizes'] and q['correct_answer']['compiles'] == compiles]
            ps = [answers[q['question_id']]['response']['answers']['synthesizes']['noul'] for q in subset]
            hits = sum(p < 0.5 for p in ps)
            # AUROC of the 99 synthesis successes against this failure subset (ties count half).
            auroc = sum(1 if a > b else .5 if a == b else 0 for a in successes for b in ps) / (len(successes) * len(ps))
            data['synthesis_failure_subsets']['compiler_accepts' if compiles else 'compiler_rejects'] = {
                'correct': hits, 'n': len(subset), 'auroc_vs_successes': auroc, 'min_p': min(ps), 'max_p': max(ps)}
        detected = correct = both = 0
        for q in reasons:
            a = answers[q['question_id']]['response']['answers']['reason']['choice']
            d = answers[q['question_id'].replace(':reason:', ':basic:')]['response']['answers']['synthesizes']['noul'] < 0.5
            c = a == q['correct_answer']['reason']
            detected += d; correct += c; both += d and c
            cls = q['correct_answer']['reason']
            counter = data['reason_by_class'].setdefault(cls, {'n': 0, 'correct': 0, 'predictions': {}})
            counter['n'] += 1; counter['correct'] += c
            counter['predictions'][a] = counter['predictions'].get(a, 0) + 1
        data['reason_linked'] = {'n': len(reasons), 'detected': detected, 'reason_correct': correct, 'both': both}
        for key in ['smaller_area', 'lower_power', 'higher_reach']:
            pairs = defaultdict(list)
            for q in test:
                if q['request'] == 'pair' and key in q['questions']:
                    pairs[q['question_id'].rsplit(':', 1)[0]].append(
                        answers[q['question_id']]['response']['answers'][key]['choice'] == q['correct_answer'][key])
            assert all(len(v) == 2 for v in pairs.values())
            counts = Counter(sum(v) for v in pairs.values())
            data['pair_counts'][key] = {'pairs': len(pairs), 'both_correct': counts[2],
                                        'one_correct': counts[1], 'neither_correct': counts[0]}
        out['models'][model] = data
    return out


def save(out):
    dest = ROOT / 'presentations/data'
    dest.mkdir(parents=True, exist_ok=True)
    (dest / 'verified_metrics.json').write_text(json.dumps(out, indent=2) + '\n')
    with (dest / 'metrics_by_test.csv').open('w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['model', 'test', 'test_questions', 'accuracy', 'balanced_accuracy', 'within_one_level', 'mean_absolute_error_expected_level', 'brier', 'auroc'])
        for model, data in out['models'].items():
            for key, t in data['table'].items():
                w.writerow([model, key, t['n'], t['accuracy'], t['balanced_accuracy'], t.get('within_one'), t.get('mae_levels'), t.get('brier'), t.get('auroc')])
    print('Verified all four answer files, 725 held-out questions each, class splits and pair orders.')
    print('Saved presentations/data/verified_metrics.json and metrics_by_test.csv')


if __name__ == '__main__':
    save(analyse())
