"""Reproduce the deck's numbers directly from the saved KEV responses."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from harness.score import predicted_level, score

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


FEWSHOT_STAMP = '20261016'


def mcnemar_p(b, c):
    """The exact two-sided McNemar p value: a binomial test of b against b + c with p = 0.5."""
    n = b + c
    return 1.0 if n == 0 else min(1.0, 2 * sum(math.comb(n, k) for k in range(min(b, c) + 1)) / 2 ** n)


def is_correct(question, truth, answer):
    """The rule of harness/score.py: a yes probability of 0.5 or more is yes; a score answer is its most likely level."""
    if question['type'] == 'noul':
        return (answer['noul'] >= 0.5) == truth
    if question['type'] == 'choice':
        return answer['choice'] == truth
    return predicted_level(answer, question['criteria'])[0] == truth


def analyse_fewshot(base):
    """Experiment 2 (2026-10-16): the 725 test questions of dataset v1, one question per request, each
    with three solved development examples in the new first state field `examples`."""
    qpath = ROOT / 'data/questions/dataset_v1_fewshot3.jsonl'
    v1path = ROOT / 'data/questions/dataset_v1.jsonl'
    allq = [json.loads(l) for l in qpath.read_text().splitlines()]
    byid = {q['question_id']: q for q in allq}
    v1 = {q['question_id']: q for q in map(json.loads, v1path.read_text().splitlines())}
    assert hashlib.sha256(v1path.read_bytes()).hexdigest() == base['dataset_sha256']
    assert len(allq) == len(byid) == 725
    assert all(q['split'] == 'test' and len(q['questions']) == 1 for q in allq)
    # Each question is a test question of dataset v1: same question, same correct answer, and the same
    # state with only the new first field `examples`.
    source = {}
    for q in allq:
        (key,) = q['questions']
        s = v1[q['source_question_id']]
        assert s['split'] == 'test' and s['questions'][key] == q['questions'][key]
        assert s['correct_answer'][key] == q['correct_answer'][key]
        assert list(q['state'])[0] == 'examples' and list(q['state'])[1:] == list(s['state'])
        assert {k: v for k, v in q['state'].items() if k != 'examples'} == s['state']
        source[(q['source_question_id'], key)] = q['question_id']
    assert set(source) == {(qid, k) for qid, s in v1.items() if s['split'] == 'test' for k in s['questions']}
    # One fixed example text per question key. The example designs are development designs, and no
    # test design shares a base design with an example (VERIFICATION.md item 14 also checks the function).
    dev = {}
    for s in v1.values():
        if s['split'] == 'dev':
            dev.setdefault(s['design_id'], {})[s['request']] = s
    test_bases = {s['base_design_id'] for s in v1.values() if s['split'] == 'test'}
    examples = {}
    for q in allq:
        (key,) = q['questions']
        ex = (q['examples']['set'], q['examples']['designs'], q['state']['examples'])
        assert examples.setdefault(key, ex) == ex
        assert all(d in dev for d in ex[1])
        assert not {dev[d]['basic']['base_design_id'] for d in ex[1]} & test_bases
    # The answer of each example, as the model reads it, checked against the development records.
    shown = {}
    for key, (exset, designs, text) in examples.items():
        blocks = text.split('\n\nExample ')[1:]
        assert len(blocks) == len(designs) == 3
        rows = []
        for i, (d, block) in enumerate(zip(designs, blocks), 1):
            assert block.startswith(f'{i}. Top module ')
            if key in ('compiles', 'synthesizes'):
                truth = dev[d]['basic']['correct_answer'][key]
                assert ('\nCorrect answer: yes.' in block) == truth and ('\nCorrect answer: no.' in block) != truth
                # A failed example also shows the first vlog or DC error (MV accepted this addition).
                assert ('The first error: ' in block) != truth
                rows.append({'design': d, 'answer': 'yes' if truth else 'no'})
            elif key == 'reason':
                truth = dev[d]['reason']['correct_answer']['reason']
                assert f'\nCorrect answer: {truth}. The first error: ' in block
                rows.append({'design': d, 'answer': truth})
            else:
                metric = {'smaller_area': 'area', 'lower_power': 'power', 'higher_reach': 'reach'}.get(key, key)
                perf = dev[d]['performance']
                level = perf['correct_answer'][metric]
                criteria = next(s['questions'][metric]['criteria'] for s in v1.values() if metric in s['questions'])
                result = block[block.index('\nResult: ') + 9:].splitlines()[0]
                # Level questions show the level; pair questions show only the exact value (MV, 2026-10-16).
                assert ('Level: ' + criteria[level - 1] in result) == (key == metric) and (('Level:' in result) == (key == metric))
                ev = perf['evidence']
                field, scale = {'slack': ('slack_ps', 1e-3), 'reach': ('reach_mhz', 1), 'area': ('ge', 1), 'power': ('total_power_w', 1e6)}[metric]
                value = ev[field] * scale
                rows.append({'design': d, 'level': level, 'value': value, 'result': result})
        shown[key] = {'set': exset, 'examples': rows}
    tokens = sorted(q['kev_tokens'] for q in allq)
    out = {'dataset_sha256': hashlib.sha256(qpath.read_bytes()).hexdigest(),
           'source_dataset_sha256': base['dataset_sha256'],
           'questions_per_key': dict(Counter(k for q in allq for k in q['questions'])),
           'v1_questions_per_test_request': dict(Counter(f"{s['request']}:{len(s['questions'])}" for s in v1.values() if s['split'] == 'test')),
           'examples': shown,
           'tokens': {'median': statistics.median(tokens), 'max': tokens[-1],
                      'over_8192': sorted(q['question_id'] for q in allq if q['kev_tokens'] > 8192)},
           'models': {}}
    comp = {q['design_id']: q for q in allq if 'compiles' in q['questions']}
    synth = {q['design_id']: q for q in allq if 'synthesizes' in q['questions']}
    assert comp.keys() == synth.keys() and len(synth) == 123
    reasons = [q for q in allq if q['request'] == 'reason']
    for model, _ in MODELS:
        folder = ROOT / 'results/kev' / f'dataset_v1_fewshot3_{model}_{FEWSHOT_STAMP}'
        answerpath = folder / f'dataset_v1_fewshot3__{model}.jsonl'
        rows = [json.loads(l) for l in answerpath.read_text().splitlines()]
        answers = {r['question_id']: r for r in rows}
        assert len(rows) == len(answers) == 725 and set(answers) == set(byid)
        assert all(a.get('status') == 200 and not a.get('error') for a in rows)
        assert all(set(a['response']['answers']) == set(byid[a['question_id']]['questions']) for a in rows)
        assert all(a['response']['usage']['input_tokens'] == byid[a['question_id']]['kev_tokens'] for a in rows)
        saved = json.loads(Path(str(answerpath) + '.score.json').read_text())
        table, missing = score(qpath, 'kev', split='test', answers_file=answerpath)
        assert missing == saved['missing'] == 0 and close(table, saved['table'])
        assert sum(t['unscored'] for t in table) == 0
        manifest = json.loads((folder / 'manifest.json').read_text())
        assert manifest['dataset_sha256'] == out['dataset_sha256'] and manifest['source_dataset_sha256'] == base['dataset_sha256']
        assert manifest['return_value'] == 0 and manifest['requests_answered'] == 725 and manifest['errors'] == 0
        # Job time as in the first run (condor_execution_seconds there): TimeExecute of the Condor job log.
        log = (ROOT / 'condor/logs' / f"{manifest['job_id']}.{model}.log").read_text()
        execute = [int(l.split(':')[1]) for l in log.splitlines() if l.strip().startswith('TimeExecute (s)')]
        assert len(execute) == 1
        manifest = dict(manifest, condor_execution_seconds=float(execute[0]))
        smoke = [json.loads(l) for l in (folder / f'dataset_v1_fewshot3_smoke__{model}.jsonl').read_text().splitlines()]
        assert sorted(r['question_id'] for r in smoke) == sorted(manifest['smoke_ids'])
        assert all(r.get('status') == 200 and not r.get('error') for r in smoke)

        def ans(q, key):
            return answers[q['question_id']]['response']['answers'][key]
        data = {'table': {t['key']: t for t in table}, 'manifest': manifest,
                'answers_file': str(answerpath.relative_to(ROOT)),
                'answers_sha256': hashlib.sha256(answerpath.read_bytes()).hexdigest(),
                'binary': {}, 'noul': {}, 'reason_by_class': {}, 'pair_counts': {}, 'pair_letters': {}}
        for key, recs in [('compiles', comp), ('synthesizes', synth)]:
            counts = Counter()
            probs = {'pass': [], 'fail': []}
            for q in recs.values():
                p = ans(q, key)['noul']
                counts[(q['correct_answer'][key], p >= 0.5)] += 1
                probs['pass' if q['correct_answer'][key] else 'fail'].append([q['question_id'], p])
            tp, fn, tn, fp = [counts[k] for k in [(True, True), (True, False), (False, False), (False, True)]]
            data['binary'][key] = dict(pass_correct=tp, pass_wrong=fn, fail_correct=tn, fail_wrong=fp,
                                        n_pass=tp + fn, n_fail=tn + fp,
                                        pass_rate=tp / (tp + fn), fail_rate=tn / (tn + fp),
                                        yes_answers=tp + fp)
            data['noul'][key] = probs
        data['no_compile_but_synthesizes'] = sum(
            ans(comp[d], 'compiles')['noul'] < 0.5 <= ans(synth[d], 'synthesizes')['noul'] for d in synth)
        data['synthesis_failure_subsets'] = {}
        successes = [ans(q, 'synthesizes')['noul'] for q in synth.values() if q['correct_answer']['synthesizes']]
        for compiles in [True, False]:
            subset = [q for d, q in synth.items()
                      if not q['correct_answer']['synthesizes'] and comp[d]['correct_answer']['compiles'] == compiles]
            ps = [ans(q, 'synthesizes')['noul'] for q in subset]
            auroc = sum(1 if a > b else .5 if a == b else 0 for a in successes for b in ps) / (len(successes) * len(ps))
            data['synthesis_failure_subsets']['compiler_accepts' if compiles else 'compiler_rejects'] = {
                'correct': sum(p < 0.5 for p in ps), 'n': len(ps), 'auroc_vs_successes': auroc, 'min_p': min(ps), 'max_p': max(ps)}
        detected = correct = both = 0
        for q in reasons:
            a = ans(q, 'reason')['choice']
            d = ans(synth[q['design_id']], 'synthesizes')['noul'] < 0.5
            c = a == q['correct_answer']['reason']
            detected += d; correct += c; both += d and c
            counter = data['reason_by_class'].setdefault(q['correct_answer']['reason'], {'n': 0, 'correct': 0, 'predictions': {}})
            counter['n'] += 1; counter['correct'] += c
            counter['predictions'][a] = counter['predictions'].get(a, 0) + 1
        data['reason_linked'] = {'n': len(reasons), 'detected': detected, 'reason_correct': correct, 'both': both}
        for key in ['smaller_area', 'lower_power', 'higher_reach']:
            pairs = defaultdict(dict)
            for q in allq:
                if key in q['questions']:
                    pair_id, order = q['question_id'].rsplit(':', 1)
                    pairs[pair_id][order] = (ans(q, key)['choice'], q['correct_answer'][key])
            assert all(set(v) == {'AB', 'BA'} for v in pairs.values())
            counts = Counter(sum(a == t for a, t in v.values()) for v in pairs.values())
            data['pair_counts'][key] = {'pairs': len(pairs), 'both_correct': counts[2], 'one_correct': counts[1],
                                        'neither_correct': counts[0],
                                        'same_letter': sum(v['AB'][0] == v['BA'][0] for v in pairs.values())}
            data['pair_letters'][key] = dict(Counter(a for v in pairs.values() for a, _ in v.values()))
        out['models'][model] = data
    # Experiment 1 against experiment 2, question by question (the rule of harness/compare.py).
    out['compare'] = {}
    for model, _ in MODELS:
        a1 = {r['question_id']: r['response']['answers'] for r in map(json.loads, (ROOT / base['models'][model]['answers_file']).read_text().splitlines())}
        a2 = {r['question_id']: r['response']['answers'] for r in map(json.loads, (ROOT / out['models'][model]['answers_file']).read_text().splitlines())}
        per_key = defaultdict(list)
        for (sid, key), fid in source.items():
            q, truth = v1[sid]['questions'][key], v1[sid]['correct_answer'][key]
            per_key[key].append((str(truth), is_correct(q, truth, a1[sid][key]), is_correct(q, truth, a2[fid][key])))
        rows = {}
        for key, rs in per_key.items():
            def bal(i):
                by_class = defaultdict(list)
                for r in rs:
                    by_class[r[0]].append(r[i])
                return sum(sum(v) / len(v) for v in by_class.values()) / len(by_class)
            b = sum(x and not y for _, x, y in rs)
            c = sum(y and not x for _, x, y in rs)
            rows[key] = {'n': len(rs), 'correct_1': sum(x for _, x, _ in rs), 'correct_2': sum(y for _, _, y in rs),
                         'balanced_1': bal(1), 'balanced_2': bal(2), 'only_1': b, 'only_2': c, 'mcnemar_p': mcnemar_p(b, c)}
            if key in ('compiles', 'synthesizes'):
                # The same paired test within each tool class (yes designs, no designs).
                rows[key]['by_class'] = {}
                for truth in ['True', 'False']:
                    cls = [r for r in rs if r[0] == truth]
                    bc, cc = sum(x and not y for _, x, y in cls), sum(y and not x for _, x, y in cls)
                    rows[key]['by_class'][truth] = {'n': len(cls), 'correct_1': sum(x for _, x, _ in cls),
                                                    'correct_2': sum(y for _, _, y in cls), 'only_1': bc, 'only_2': cc,
                                                    'mcnemar_p': mcnemar_p(bc, cc)}
            # The same numbers as the scorer of each run and as harness/compare.py.
            assert math.isclose(rows[key]['correct_1'] / len(rs), base['models'][model]['table'][key]['accuracy'])
            assert math.isclose(rows[key]['correct_2'] / len(rs), out['models'][model]['table'][key]['accuracy'])
            assert math.isclose(rows[key]['balanced_1'], base['models'][model]['table'][key]['balanced_accuracy'])
            assert math.isclose(rows[key]['balanced_2'], out['models'][model]['table'][key]['balanced_accuracy'])
        saved = json.loads((ROOT / f'results/kev/dataset_v1_fewshot3_{model}_{FEWSHOT_STAMP}/compare_with_dataset_v1.json').read_text())
        assert saved['matched'] == 725
        for t in saved['table']:
            r = rows[t['key']]
            assert (t['n'], t['only_base_correct'], t['only_new_correct']) == (r['n'], r['only_1'], r['only_2'])
            assert math.isclose(t['mcnemar_p'], r['mcnemar_p'])
        reason_1 = Counter(a1[q['source_question_id']]['reason']['choice'] for q in reasons)
        out['compare'][model] = {'keys': rows, 'reason_predictions_1': dict(reason_1)}
    return out


def save_fewshot(out):
    dest = ROOT / 'presentations/data'
    (dest / 'verified_metrics_fewshot3.json').write_text(json.dumps(out, indent=2) + '\n')
    with (dest / 'metrics_by_test_fewshot3.csv').open('w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['model', 'test', 'test_questions', 'accuracy', 'balanced_accuracy', 'within_one_level', 'mean_absolute_error_expected_level', 'brier', 'auroc'])
        for model, data in out['models'].items():
            for key, t in data['table'].items():
                w.writerow([model, key, t['n'], t['accuracy'], t['balanced_accuracy'], t.get('within_one'), t.get('mae_levels'), t.get('brier'), t.get('auroc')])
    with (dest / 'compare_fewshot3.csv').open('w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['model', 'test', 'test_questions', 'correct_no_examples', 'correct_with_examples',
                    'balanced_no_examples', 'balanced_with_examples', 'correct_only_no_examples', 'correct_only_with_examples', 'mcnemar_p'])
        for model, c in out['compare'].items():
            for key, r in sorted(c['keys'].items()):
                w.writerow([model, key, r['n'], r['correct_1'], r['correct_2'], r['balanced_1'], r['balanced_2'], r['only_1'], r['only_2'], r['mcnemar_p']])
    print('Verified the four few-shot answer files (725 questions each) and the comparison with the first run.')
    print('Saved presentations/data/verified_metrics_fewshot3.json, metrics_by_test_fewshot3.csv and compare_fewshot3.csv')


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
    base = analyse()
    save(base)
    save_fewshot(analyse_fewshot(base))
