from __future__ import annotations

import csv
import json
import math
import re
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from typing import Any, Iterable, Optional
from urllib.parse import parse_qs, unquote_plus, urlparse

from django.core.management.base import BaseCommand, CommandError
from django.db import models

from task_manager.models import PostTaskAnnotation, Task, TaskTrial, Webpage


class Command(BaseCommand):
    help = "Analyzes navigation topology patterns in tasks (beyond star vs chain)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--format",
            choices=["text", "json"],
            default="text",
            help="Output format (default: text).",
        )
        parser.add_argument(
            "--min-pages",
            type=int,
            default=3,
            help="Minimum number of recorded Webpage visits per task (default: 3).",
        )
        parser.add_argument(
            "--max-tasks",
            type=int,
            default=None,
            help="Optional cap on number of tasks analyzed.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=200,
            help="Batch size for fetching tasks/pages (default: 200).",
        )
        parser.add_argument(
            "--progress-every",
            type=int,
            default=200,
            help="Log progress every N tasks (default: 200).",
        )
        parser.add_argument(
            "--csv",
            type=str,
            default=None,
            help="Optional path to write per-task metrics as CSV.",
        )
        parser.add_argument(
            "--include-annotations",
            action="store_true",
            help="Include post-task self-report fields (e.g., unhelpful paths) in CSV.",
        )
        parser.add_argument(
            "--explain",
            action="store_true",
            help="Print plain-language explanations of each metric.",
        )

    def handle(self, *args, **options):
        style = self.style
        heading_style = getattr(style, "MIGRATE_HEADING", style.SUCCESS)
        label_style = getattr(style, "MIGRATE_LABEL", lambda s: s)
        value_style = getattr(style, "SQL_FIELD", lambda s: s)
        dim_style = getattr(style, "SQL_TABLE", lambda s: s)

        def heading(text: str):
            self.stdout.write(heading_style(text))

        output_format: str = options["format"]
        min_pages: int = options["min_pages"]
        max_tasks: Optional[int] = options["max_tasks"]
        batch_size: int = options["batch_size"]
        progress_every: int = options["progress_every"]
        csv_path: Optional[str] = options["csv"]
        include_annotations: bool = options["include_annotations"]
        explain: bool = options["explain"]

        if min_pages < 2:
            raise CommandError("--min-pages must be >= 2.")
        if batch_size < 1:
            raise CommandError("--batch-size must be >= 1.")

        base_tasks_qs = (
            Task.objects.annotate(page_count=models.Count("webpage"))
            .filter(page_count__gte=min_pages)
            .order_by("-id")
        )
        if max_tasks is not None:
            base_tasks_qs = base_tasks_qs[:max_tasks]

        task_ids = list(base_tasks_qs.values_list("id", flat=True))
        total_tasks = len(task_ids)
        if output_format == "text":
            heading("Topology Analysis")
            self.stdout.write(
                dim_style(
                    f"Filters: min_pages={min_pages}"
                    + (f", max_tasks={max_tasks}" if max_tasks is not None else "")
                    + f", batch_size={batch_size}"
                )
            )
            self.stdout.write(f"{label_style('Tasks found:')} {value_style(str(total_tasks))}")

        writer = None
        csv_fh = None
        if csv_path:
            csv_fh = open(csv_path, "w", newline="", encoding="utf-8")
            writer = csv.DictWriter(csv_fh, fieldnames=_csv_fieldnames(include_annotations))
            writer.writeheader()

        try:
            aggregated = _Aggregates()
            circular_groups = _CircularGroups()

            processed = 0
            for batch_ids in _iter_list_in_batches(task_ids, batch_size=batch_size):
                tasks = Task.objects.filter(id__in=batch_ids).only("id", "user_id")

                pages_by_task: dict[int, list[Webpage]] = defaultdict(list)
                for p in (
                    Webpage.objects.filter(belong_task_id__in=batch_ids)
                    .order_by("id")
                    .only(
                        "id",
                        "belong_task_id",
                        "url",
                        "referrer",
                        "start_timestamp",
                        "end_timestamp",
                        "dwell_time",
                    )
                ):
                    pages_by_task[p.belong_task_id].append(p)

                trials_by_task: dict[int, list[TaskTrial]] = defaultdict(list)
                for t in (
                    TaskTrial.objects.filter(belong_task_id__in=batch_ids)
                    .order_by("num_trial", "id")
                    .only("id", "belong_task_id", "num_trial", "is_correct", "confidence")
                ):
                    trials_by_task[t.belong_task_id].append(t)

                post_by_task: dict[int, PostTaskAnnotation] = {}
                post_fields = ["belong_task_id", "unhelpful_paths"]
                if include_annotations:
                    post_fields.append("strategy_shift")
                for post in PostTaskAnnotation.objects.filter(belong_task_id__in=batch_ids).only(
                    *post_fields
                ):
                    post_by_task[post.belong_task_id] = post

                for task in tasks:
                    processed += 1
                    if output_format == "text" and progress_every and processed % progress_every == 0:
                        self.stdout.write(dim_style(f"Processed {processed}/{total_tasks} tasks..."))

                    pages = pages_by_task.get(task.id, [])
                    if len(pages) < min_pages:
                        continue

                    metrics = _analyze_task_pages(
                        pages=pages, trials=trials_by_task.get(task.id, [])
                    )

                    aggregated.add(metrics)

                    self_report_circular: Optional[bool] = None
                    annotation_unhelpful_paths = None
                    annotation_strategy_shift = None
                    post = post_by_task.get(task.id)
                    if post is not None:
                        self_report_circular = bool(
                            post.unhelpful_paths
                            and "circular_navigation" in set(post.unhelpful_paths)
                        )
                        if include_annotations:
                            annotation_unhelpful_paths = post.unhelpful_paths
                            annotation_strategy_shift = post.strategy_shift

                    circular_groups.add(metrics=metrics, self_report_circular=self_report_circular)

                    if writer:
                        row = metrics.to_row(
                            task_id=task.id,
                            user_id=task.user_id,
                            include_annotations=include_annotations,
                            annotation_unhelpful_paths=annotation_unhelpful_paths,
                            annotation_strategy_shift=annotation_strategy_shift,
                            self_report_circular=self_report_circular,
                        )
                        writer.writerow(row)

            if aggregated.count == 0:
                if output_format == "json":
                    self.stdout.write(
                        json.dumps(
                            {
                                "filters": {
                                    "min_pages": min_pages,
                                    "max_tasks": max_tasks,
                                    "batch_size": batch_size,
                                },
                                "tasks_found": total_tasks,
                                "tasks_analyzed": 0,
                            },
                            indent=2,
                            sort_keys=True,
                        )
                    )
                return

            if output_format == "json":
                report: dict[str, Any] = {
                    "filters": {
                        "min_pages": min_pages,
                        "max_tasks": max_tasks,
                        "batch_size": batch_size,
                    },
                    "tasks_found": total_tasks,
                    "tasks_analyzed": aggregated.count,
                    "summary": aggregated.summary_dict(),
                    "archetypes": aggregated.archetype_dict(),
                    "outcomes": aggregated.outcome_dict(),
                    "self_report_circular": circular_groups.summary_dict(),
                }
                if explain:
                    report["metric_explanations"] = _metric_explanations_dict()
                    report["archetype_explanations"] = _archetype_explanations_dict()
                    report["interpretation_notes"] = _interpretation_notes()
                if csv_path:
                    report["csv_written"] = csv_path
                self.stdout.write(json.dumps(report, indent=2, sort_keys=True))
                return

            self.stdout.write("")
            self.stdout.write(f"{label_style('Tasks analyzed:')} {value_style(str(aggregated.count))}")

            self.stdout.write("")
            heading("Topology Summary")
            for line in aggregated.summary_lines():
                self.stdout.write(
                    _stylize_summary_line(
                        line=line,
                        label_style=label_style,
                        value_style=value_style,
                        dim_style=dim_style,
                    )
                )

            self.stdout.write("")
            heading("Outcome Slice (Final Trial)")
            for line in aggregated.outcome_lines():
                self.stdout.write(dim_style(line))

            self.stdout.write("")
            heading("Archetype Breakdown")
            archetype_label_width = max(
                16, max((len(a) for a in aggregated.archetype_counts.keys()), default=0) + 1
            )
            for line in aggregated.archetype_lines():
                parsed = _parse_archetype_line(line)
                if not parsed:
                    self.stdout.write(line)
                    continue
                name, count, pct = parsed
                bar = _bar(pct, width=24)
                pct_text = f"{pct*100:5.1f}%"
                name_label = f"{name}:"
                self.stdout.write(
                    f"{label_style(f'{name_label:<{archetype_label_width}}')} {dim_style(bar)} {value_style(pct_text)} {dim_style(f'({count})')}"
                )

            self.stdout.write("")
            heading("Archetype × Outcome (Final Trial)")
            for line in aggregated.archetype_outcome_lines():
                self.stdout.write(dim_style(line))

            self.stdout.write("")
            heading("Self-Report Check: Circular Navigation")
            for line in circular_groups.summary_lines():
                if line.startswith("Annotated tasks:"):
                    self.stdout.write(value_style(line))
                else:
                    self.stdout.write(dim_style(line))

            if explain:
                self.stdout.write("")
                heading("Metric Explanations")
                for key, desc in _metric_explanations_dict().items():
                    key_label = f"{key}:"
                    self.stdout.write(f"{label_style(f'{key_label:<26}')} {desc}")

                self.stdout.write("")
                heading("Archetype Explanations")
                for key, desc in _archetype_explanations_dict().items():
                    key_label = f"{key}:"
                    self.stdout.write(f"{label_style(f'{key_label:<26}')} {desc}")

                self.stdout.write("")
                heading("Interpretation Notes")
                for line in _interpretation_notes():
                    self.stdout.write(dim_style(f"- {line}"))

            if csv_path:
                self.stdout.write("")
                self.stdout.write(f"{label_style('CSV written:')} {value_style(csv_path)}")

            self.stdout.write(dim_style("-" * 60))
        finally:
            if csv_fh:
                csv_fh.close()


_ARCHETYPE_RE = re.compile(r"^(?P<name>[^:]+):\s+(?P<count>\d+)\s+\((?P<pct>[\d.]+)%\)\s*$")
_NUMBER_RE = re.compile(r"(-?\d+(?:\.\d+)?)")


def _parse_archetype_line(line: str) -> Optional[tuple[str, int, float]]:
    m = _ARCHETYPE_RE.match(line)
    if not m:
        return None
    return m.group("name"), int(m.group("count")), float(m.group("pct")) / 100.0


def _bar(pct: float, *, width: int = 20) -> str:
    pct = min(1.0, max(0.0, pct))
    filled = int(round(pct * width))
    return "█" * filled + "░" * (width - filled)


def _stylize_summary_line(*, label_style, value_style, dim_style, line: str) -> str:
    def color_numbers(s: str) -> str:
        return _NUMBER_RE.sub(lambda m: value_style(m.group(1)), s)

    if ":" not in line:
        return color_numbers(line)

    label, rest = line.split(":", 1)
    rest = rest.strip()
    rest = color_numbers(rest)
    rest = rest.replace("mean=", dim_style("mean="))
    rest = rest.replace("median=", dim_style("median="))
    rest = rest.replace("p90=", dim_style("p90="))
    rest = rest.replace("IQR=", dim_style("IQR="))
    label_text = f"{label}:"
    label_padded = f"{label_text:<22}"
    return f"{label_style(label_padded)} {rest}"


def _iter_list_in_batches(items: list[int], *, batch_size: int):
    for i in range(0, len(items), batch_size):
        yield items[i : i + batch_size]


def _normalize_netloc(netloc: str) -> str:
    n = (netloc or "").strip().lower()
    if n.startswith("www."):
        n = n[4:]
    return n


def _clean_query(q: Optional[str]) -> Optional[str]:
    if not q:
        return None
    decoded = unquote_plus(q).lower().strip()
    decoded = " ".join(decoded.split())
    return decoded or None


def _parse_serp(url: str) -> tuple[Optional[str], Optional[str]]:
    try:
        parsed = urlparse(url)
    except Exception:
        return None, None

    netloc = _normalize_netloc(parsed.netloc)
    params = parse_qs(parsed.query)

    if "google." in netloc and parsed.path.startswith("/search"):
        return "google", _clean_query(params.get("q", [None])[0])
    if netloc.endswith("bing.com") and parsed.path.startswith("/search"):
        return "bing", _clean_query(params.get("q", [None])[0])
    if netloc.endswith("baidu.com") and parsed.path.startswith("/s"):
        return "baidu", _clean_query(params.get("wd", [None])[0])
    if netloc in {"duckduckgo.com"}:
        return "duckduckgo", _clean_query(params.get("q", [None])[0])
    if netloc.endswith("search.yahoo.com"):
        return "yahoo", _clean_query(params.get("p", [None])[0])

    return None, None


def _normalize_url_for_graph(url: str) -> str:
    try:
        parsed = urlparse(url)
    except Exception:
        return (url or "").strip()

    netloc = _normalize_netloc(parsed.netloc)
    path = parsed.path or ""
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    return f"{netloc}{path}"


def _node_key(url: str) -> tuple[str, str, str]:
    engine, query = _parse_serp(url)
    if engine and query:
        return f"serp:{engine}:{query}", "serp", engine
    return f"url:{_normalize_url_for_graph(url)}", "url", ""


def _domain(url: str) -> str:
    try:
        return _normalize_netloc(urlparse(url).netloc)
    except Exception:
        return ""

def _is_serp_key(key: str) -> bool:
    return key.startswith("serp:")


def _shannon_entropy(counts: Counter[str]) -> float:
    total = sum(counts.values())
    if total <= 0:
        return 0.0
    h = 0.0
    for c in counts.values():
        if c <= 0:
            continue
        p = c / total
        h -= p * math.log2(p)
    return h


def _normalized_entropy(counts: Counter[str]) -> float:
    if not counts:
        return 0.0
    h = _shannon_entropy(counts)
    max_h = math.log2(len(counts)) if len(counts) > 1 else 1.0
    return h / max_h if max_h > 0 else 0.0


def _bfs_distances(adj: dict[str, set[str]], source: str) -> dict[str, int]:
    distances: dict[str, int] = {source: 0}
    q: deque[str] = deque([source])
    while q:
        v = q.popleft()
        for w in adj.get(v, set()):
            if w in distances:
                continue
            distances[w] = distances[v] + 1
            q.append(w)
    return distances


def _strongly_connected_components(nodes: Iterable[str], adj: dict[str, set[str]]):
    nodes_list = list(nodes)
    visited: set[str] = set()
    order: list[str] = []

    def dfs1(start: str):
        stack: list[tuple[str, Optional[Iterable[str]]]] = [(start, None)]
        while stack:
            v, it = stack.pop()
            if it is None:
                if v in visited:
                    continue
                visited.add(v)
                it = iter(adj.get(v, set()))
                stack.append((v, it))
            try:
                nxt = next(it)  # type: ignore[arg-type]
                if nxt not in visited:
                    stack.append((v, it))
                    stack.append((nxt, None))
            except StopIteration:
                order.append(v)

    for v in nodes_list:
        if v not in visited:
            dfs1(v)

    rev: dict[str, set[str]] = defaultdict(set)
    for v, outs in adj.items():
        for w in outs:
            rev[w].add(v)

    visited.clear()
    components: list[list[str]] = []

    for v in reversed(order):
        if v in visited:
            continue
        comp: list[str] = []
        stack = [v]
        visited.add(v)
        while stack:
            x = stack.pop()
            comp.append(x)
            for y in rev.get(x, set()):
                if y in visited:
                    continue
                visited.add(y)
                stack.append(y)
        components.append(comp)
    return components


@dataclass(frozen=True)
class TaskTopologyMetrics:
    n_visits: int
    n_nodes: int
    n_edges: int
    n_unique_domains: int
    revisit_rate: float
    aba_backtrack_rate: float
    scc_nodes_fraction: float
    content_revisit_rate: float
    content_aba_backtrack_rate: float
    content_scc_nodes_fraction: float
    reachable_fraction_from_root: float
    depth_max: int
    depth_p90: float
    branching_factor_mean: float
    hub_dominance: float
    serp_visits: int
    serp_episode_fanout_mean: float
    serp_return_rate: float
    serp_transition_rate: float
    domain_entropy_norm: float
    dominant_visit_share: float
    dominant_is_serp: bool
    final_is_correct: Optional[bool]
    archetype: str

    def to_row(
        self,
        *,
        task_id: int,
        user_id: int,
        include_annotations: bool,
        annotation_unhelpful_paths: Any,
        annotation_strategy_shift: Any,
        self_report_circular: Optional[bool],
    ) -> dict[str, Any]:
        row: dict[str, Any] = {
            "task_id": task_id,
            "user_id": user_id,
            **self.__dict__,
        }
        if include_annotations:
            row["unhelpful_paths"] = annotation_unhelpful_paths
            row["strategy_shift"] = annotation_strategy_shift
            row["self_report_circular_navigation"] = self_report_circular
        return row


def _csv_fieldnames(include_annotations: bool) -> list[str]:
    base = [
        "task_id",
        "user_id",
        "n_visits",
        "n_nodes",
        "n_edges",
        "n_unique_domains",
        "revisit_rate",
        "aba_backtrack_rate",
        "scc_nodes_fraction",
        "content_revisit_rate",
        "content_aba_backtrack_rate",
        "content_scc_nodes_fraction",
        "reachable_fraction_from_root",
        "depth_max",
        "depth_p90",
        "branching_factor_mean",
        "hub_dominance",
        "serp_visits",
        "serp_episode_fanout_mean",
        "serp_return_rate",
        "serp_transition_rate",
        "domain_entropy_norm",
        "dominant_visit_share",
        "dominant_is_serp",
        "final_is_correct",
        "archetype",
    ]
    if include_annotations:
        base += [
            "unhelpful_paths",
            "strategy_shift",
            "self_report_circular_navigation",
        ]
    return base


def _final_trial_is_correct(trials: list[TaskTrial]) -> Optional[bool]:
    if not trials:
        return None
    final = max(trials, key=lambda t: (t.num_trial, t.id))
    return final.is_correct


def _analyze_task_pages(*, pages: list[Webpage], trials: list[TaskTrial]) -> TaskTopologyMetrics:
    def sort_key(p: Webpage):
        ts = p.start_timestamp
        return (ts is None, ts, p.id)

    pages_sorted = sorted(pages, key=sort_key)

    keys: list[str] = []
    domains: list[str] = []
    kinds: list[str] = []
    serp_indices: list[int] = []

    for idx, p in enumerate(pages_sorted):
        k, kind, _engine = _node_key(p.url)
        keys.append(k)
        kinds.append(kind)
        domains.append(_domain(p.url))
        if kind == "serp":
            serp_indices.append(idx)

    n_visits = len(keys)
    unique_nodes = set(keys)
    n_nodes = len(unique_nodes)

    if n_visits < 2 or n_nodes == 0:
        return TaskTopologyMetrics(
            n_visits=n_visits,
            n_nodes=n_nodes,
            n_edges=0,
            n_unique_domains=len(set(domains)) if domains else 0,
            revisit_rate=0.0,
            aba_backtrack_rate=0.0,
            scc_nodes_fraction=0.0,
            content_revisit_rate=0.0,
            content_aba_backtrack_rate=0.0,
            content_scc_nodes_fraction=0.0,
            reachable_fraction_from_root=0.0,
            depth_max=0,
            depth_p90=0.0,
            branching_factor_mean=0.0,
            hub_dominance=0.0,
            serp_visits=len(serp_indices),
            serp_episode_fanout_mean=0.0,
            serp_return_rate=0.0,
            serp_transition_rate=0.0,
            domain_entropy_norm=_normalized_entropy(Counter(domains)),
            dominant_visit_share=1.0 if n_visits else 0.0,
            dominant_is_serp=bool(serp_indices),
            final_is_correct=_final_trial_is_correct(trials),
            archetype="degenerate",
        )

    revisit_rate = 1.0 - (n_nodes / n_visits)

    aba = 0
    for i in range(n_visits - 2):
        if keys[i] == keys[i + 2] and keys[i] != keys[i + 1]:
            aba += 1
    aba_backtrack_rate = aba / (n_visits - 2) if n_visits > 2 else 0.0

    edge_counts: Counter[tuple[str, str]] = Counter()
    adj: dict[str, set[str]] = defaultdict(set)
    for a, b in zip(keys, keys[1:]):
        edge_counts[(a, b)] += 1
        adj[a].add(b)
    n_edges = len(edge_counts)

    out_degrees = {n: len(adj.get(n, set())) for n in unique_nodes}
    out_nonzero = [d for d in out_degrees.values() if d > 0]
    branching_factor_mean = sum(out_nonzero) / len(out_nonzero) if out_nonzero else 0.0

    max_out = max(out_degrees.values()) if out_degrees else 0
    hub_dominance = max_out / (n_nodes - 1) if n_nodes > 1 else 0.0

    sccs = _strongly_connected_components(unique_nodes, adj)
    scc_nodes = 0
    for comp in sccs:
        if len(comp) > 1:
            scc_nodes += len(comp)
    scc_nodes_fraction = (scc_nodes / n_nodes) if n_nodes else 0.0

    content_revisit_rate, content_aba_backtrack_rate, content_scc_nodes_fraction = (
        _content_loop_metrics(keys, kinds)
    )

    root = keys[0]

    ref_adj: dict[str, set[str]] = defaultdict(set)
    node_set = set(keys)
    for p in pages_sorted:
        if not p.referrer:
            continue
        src, _, _ = _node_key(p.referrer)
        dst, _, _ = _node_key(p.url)
        if src == dst:
            continue
        if src in node_set and dst in node_set:
            ref_adj[src].add(dst)

    distances = _bfs_distances(ref_adj, root) if root in node_set else {}
    reachable_fraction_from_root = len(distances) / n_nodes if n_nodes else 0.0
    depth_max = max(distances.values()) if distances else 0

    dist_vals = sorted(distances.values()) if distances else [0]
    depth_p90 = _percentile(dist_vals, 90)

    serp_visits = len(serp_indices)
    serp_episode_fanout_mean, serp_return_rate = _serp_episode_stats(keys, serp_indices)
    transitions = list(zip(kinds, kinds[1:]))
    serp_transition_rate = (
        sum(1 for a, b in transitions if a == "serp" or b == "serp") / len(transitions)
        if transitions
        else 0.0
    )

    visit_counts = Counter(keys)
    dominant_key, dominant_count = visit_counts.most_common(1)[0]
    dominant_visit_share = dominant_count / n_visits if n_visits else 0.0
    dominant_is_serp = _is_serp_key(dominant_key)

    domain_counts = Counter(d for d in domains if d)
    n_unique_domains = len(domain_counts)
    domain_entropy_norm = _normalized_entropy(domain_counts)

    final_is_correct = _final_trial_is_correct(trials)

    archetype = _classify_archetype(
        n_nodes=n_nodes,
        hub_dominance=hub_dominance,
        depth_max=depth_max,
        branching_factor_mean=branching_factor_mean,
        revisit_rate=revisit_rate,
        serp_visits=serp_visits,
        serp_return_rate=serp_return_rate,
        serp_transition_rate=serp_transition_rate,
        dominant_is_serp=dominant_is_serp,
        content_revisit_rate=content_revisit_rate,
        content_aba_backtrack_rate=content_aba_backtrack_rate,
        content_scc_nodes_fraction=content_scc_nodes_fraction,
    )

    return TaskTopologyMetrics(
        n_visits=n_visits,
        n_nodes=n_nodes,
        n_edges=n_edges,
        n_unique_domains=n_unique_domains,
        revisit_rate=revisit_rate,
        aba_backtrack_rate=aba_backtrack_rate,
        scc_nodes_fraction=scc_nodes_fraction,
        content_revisit_rate=content_revisit_rate,
        content_aba_backtrack_rate=content_aba_backtrack_rate,
        content_scc_nodes_fraction=content_scc_nodes_fraction,
        reachable_fraction_from_root=reachable_fraction_from_root,
        depth_max=depth_max,
        depth_p90=depth_p90,
        branching_factor_mean=branching_factor_mean,
        hub_dominance=hub_dominance,
        serp_visits=serp_visits,
        serp_episode_fanout_mean=serp_episode_fanout_mean,
        serp_return_rate=serp_return_rate,
        serp_transition_rate=serp_transition_rate,
        domain_entropy_norm=domain_entropy_norm,
        dominant_visit_share=dominant_visit_share,
        dominant_is_serp=dominant_is_serp,
        final_is_correct=final_is_correct,
        archetype=archetype,
    )


def _percentile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    p = min(100.0, max(0.0, p))
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(sorted_vals[int(k)])
    d0 = sorted_vals[f] * (c - k)
    d1 = sorted_vals[c] * (k - f)
    return float(d0 + d1)


def _serp_episode_stats(keys: list[str], serp_indices: list[int]) -> tuple[float, float]:
    if not serp_indices:
        return 0.0, 0.0

    episodes = 0
    total_fanout = 0
    returnable = 0
    returned = 0

    serp_positions = serp_indices + [len(keys)]
    for start_idx, end_idx in zip(serp_positions, serp_positions[1:]):
        episode_keys = keys[start_idx + 1 : end_idx]
        unique_clicked = {k for k in episode_keys if not k.startswith("serp:")}
        fanout = len(unique_clicked)
        episodes += 1
        total_fanout += fanout
        if fanout > 0:
            returnable += 1
            if end_idx < len(keys):
                returned += 1

    fanout_mean = total_fanout / episodes if episodes else 0.0
    return_rate = returned / returnable if returnable else 0.0
    return fanout_mean, return_rate


def _classify_archetype(
    *,
    n_nodes: int,
    hub_dominance: float,
    depth_max: int,
    branching_factor_mean: float,
    serp_visits: int,
    revisit_rate: float,
    serp_return_rate: float,
    serp_transition_rate: float,
    dominant_is_serp: bool,
    content_revisit_rate: float,
    content_aba_backtrack_rate: float,
    content_scc_nodes_fraction: float,
) -> str:
    if n_nodes <= 1:
        return "degenerate"

    chain_score = depth_max / max(1, n_nodes - 1)

    is_serp_hub = (
        serp_visits >= 2
        and (dominant_is_serp or serp_transition_rate >= 0.40)
        and hub_dominance >= 0.50
    )
    if is_serp_hub:
        return "serp-hub"

    if hub_dominance >= 0.60:
        return "hub-spoke" if serp_visits > 0 else "star"

    if chain_score >= 0.60 and branching_factor_mean <= 1.25:
        return "chain"

    if serp_visits > 0 and serp_return_rate >= 0.50:
        return "serp-hopping"

    loop_heavy = (
        (content_scc_nodes_fraction >= 0.20 or content_aba_backtrack_rate >= 0.20)
        and content_revisit_rate >= 0.25
    )
    if loop_heavy:
        return "loop-heavy"

    return "mixed"


class _Aggregates:
    def __init__(self):
        self.count = 0
        self.metrics: list[TaskTopologyMetrics] = []
        self.archetype_counts: Counter[str] = Counter()

    def add(self, metrics: TaskTopologyMetrics):
        self.count += 1
        self.metrics.append(metrics)
        self.archetype_counts[metrics.archetype] += 1

    def _vals(self, attr: str) -> list[float]:
        return [float(getattr(m, attr)) for m in self.metrics]

    def summary_lines(self) -> list[str]:
        lines = []
        lines.append(_summ_line("Max depth", self._vals("depth_max"), unit="hops"))
        lines.append(_summ_line("P90 depth", self._vals("depth_p90"), unit="hops"))
        lines.append(_summ_line("Hub dominance", self._vals("hub_dominance"), unit=""))
        lines.append(_summ_line("Branching", self._vals("branching_factor_mean"), unit=""))
        lines.append(_summ_line("Revisit rate", self._vals("revisit_rate"), unit=""))
        lines.append(_summ_line("ABA backtrack", self._vals("aba_backtrack_rate"), unit=""))
        lines.append(_summ_line("SCC node frac", self._vals("scc_nodes_fraction"), unit=""))
        lines.append(_summ_line("Content revisit", self._vals("content_revisit_rate"), unit=""))
        lines.append(_summ_line("Content ABA", self._vals("content_aba_backtrack_rate"), unit=""))
        lines.append(_summ_line("Content SCC frac", self._vals("content_scc_nodes_fraction"), unit=""))
        lines.append(_summ_line("Domain entropy", self._vals("domain_entropy_norm"), unit=""))
        lines.append(_summ_line("SERP visits", self._vals("serp_visits"), unit=""))
        lines.append(_summ_line("SERP fanout", self._vals("serp_episode_fanout_mean"), unit=""))
        lines.append(_summ_line("SERP return", self._vals("serp_return_rate"), unit=""))
        lines.append(_summ_line("SERP transition", self._vals("serp_transition_rate"), unit=""))
        lines.append(_summ_line("Dominant visit share", self._vals("dominant_visit_share"), unit=""))
        lines.append(
            _summ_line(
                "Dominant is SERP",
                [1.0 if m.dominant_is_serp else 0.0 for m in self.metrics],
                unit="",
            )
        )

        correct_known = [m.final_is_correct for m in self.metrics if m.final_is_correct is not None]
        if correct_known:
            acc = sum(1 for v in correct_known if v) / len(correct_known)
            lines.append(f"Final-trial accuracy (where known): {acc*100:.1f}% ({len(correct_known)} tasks)")

        return lines

    def summary_dict(self) -> dict[str, Any]:
        metrics: list[tuple[str, str, str]] = [
            ("depth_max", "Max depth", "hops"),
            ("depth_p90", "P90 depth", "hops"),
            ("hub_dominance", "Hub dominance", ""),
            ("branching_factor_mean", "Branching", ""),
            ("revisit_rate", "Revisit rate", ""),
            ("aba_backtrack_rate", "ABA backtrack", ""),
            ("scc_nodes_fraction", "SCC node frac", ""),
            ("content_revisit_rate", "Content revisit", ""),
            ("content_aba_backtrack_rate", "Content ABA", ""),
            ("content_scc_nodes_fraction", "Content SCC frac", ""),
            ("domain_entropy_norm", "Domain entropy", ""),
            ("serp_visits", "SERP visits", ""),
            ("serp_episode_fanout_mean", "SERP fanout", ""),
            ("serp_return_rate", "SERP return", ""),
            ("serp_transition_rate", "SERP transition", ""),
            ("dominant_visit_share", "Dominant visit share", ""),
        ]
        out: dict[str, Any] = {}
        for attr, label, unit in metrics:
            out[attr] = {"label": label, "unit": unit, **_stats_dict(self._vals(attr))}
        out["dominant_is_serp"] = {
            "label": "Dominant is SERP",
            "unit": "",
            **_stats_dict([1.0 if m.dominant_is_serp else 0.0 for m in self.metrics]),
        }
        correct_known = [m.final_is_correct for m in self.metrics if m.final_is_correct is not None]
        out["final_is_correct"] = {
            "known": len(correct_known),
            "accuracy": (
                sum(1 for v in correct_known if v) / len(correct_known) if correct_known else None
            ),
        }
        return out

    def archetype_lines(self) -> list[str]:
        if not self.metrics:
            return []
        total = len(self.metrics)
        lines = []
        for archetype, cnt in self.archetype_counts.most_common():
            lines.append(f"{archetype}: {cnt} ({cnt/total*100:.1f}%)")
        return lines

    def archetype_dict(self) -> list[dict[str, Any]]:
        total = len(self.metrics)
        out = []
        for archetype, cnt in self.archetype_counts.most_common():
            out.append({"archetype": archetype, "count": cnt, "fraction": (cnt / total) if total else 0.0})
        return out

    def _split_by_outcome(
        self,
    ) -> tuple[list[TaskTopologyMetrics], list[TaskTopologyMetrics], list[TaskTopologyMetrics]]:
        correct: list[TaskTopologyMetrics] = []
        incorrect: list[TaskTopologyMetrics] = []
        unknown: list[TaskTopologyMetrics] = []
        for m in self.metrics:
            if m.final_is_correct is True:
                correct.append(m)
            elif m.final_is_correct is False:
                incorrect.append(m)
            else:
                unknown.append(m)
        return correct, incorrect, unknown

    def outcome_lines(self) -> list[str]:
        correct, incorrect, unknown = self._split_by_outcome()
        known = len(correct) + len(incorrect)
        if known == 0:
            return ["No final-trial correctness labels found in TaskTrial."]

        lines = [
            f"Known labels: {known} tasks (correct={len(correct)}, incorrect={len(incorrect)}), unknown={len(unknown)}",
        ]

        def mean(group: list[TaskTopologyMetrics], attr: str) -> float:
            if not group:
                return 0.0
            return sum(float(getattr(m, attr)) for m in group) / len(group)

        comparisons: list[tuple[str, str]] = [
            ("content_scc_nodes_fraction", "Content SCC frac"),
            ("content_aba_backtrack_rate", "Content ABA"),
            ("content_revisit_rate", "Content revisit"),
            ("serp_transition_rate", "SERP transition"),
            ("serp_return_rate", "SERP return"),
            ("domain_entropy_norm", "Domain entropy"),
            ("depth_max", "Max depth"),
        ]
        for attr, label in comparisons:
            if not correct or not incorrect:
                continue
            a = mean(correct, attr)
            b = mean(incorrect, attr)
            delta = b - a
            lines.append(f"{label}: correct_mean={a:.3f}, incorrect_mean={b:.3f}, Δ(incorrect-correct)={delta:+.3f}")
        return lines

    def outcome_dict(self) -> dict[str, Any]:
        correct, incorrect, unknown = self._split_by_outcome()
        known = len(correct) + len(incorrect)
        out: dict[str, Any] = {
            "counts": {"correct": len(correct), "incorrect": len(incorrect), "unknown": len(unknown)},
            "known": known,
        }
        if known == 0:
            out["note"] = "No final-trial correctness labels found in TaskTrial."
            return out

        def mean(group: list[TaskTopologyMetrics], attr: str) -> Optional[float]:
            if not group:
                return None
            return sum(float(getattr(m, attr)) for m in group) / len(group)

        comparisons: list[tuple[str, str]] = [
            ("content_scc_nodes_fraction", "Content SCC frac"),
            ("content_aba_backtrack_rate", "Content ABA"),
            ("content_revisit_rate", "Content revisit"),
            ("serp_transition_rate", "SERP transition"),
            ("serp_return_rate", "SERP return"),
            ("domain_entropy_norm", "Domain entropy"),
            ("depth_max", "Max depth"),
        ]
        out["metric_means"] = {}
        for attr, label in comparisons:
            a = mean(correct, attr)
            b = mean(incorrect, attr)
            out["metric_means"][attr] = {
                "label": label,
                "correct_mean": a,
                "incorrect_mean": b,
                "delta_incorrect_minus_correct": (b - a) if (a is not None and b is not None) else None,
            }
        out["archetype_outcomes"] = self.archetype_outcome_dict()
        return out

    def archetype_outcome_dict(self) -> list[dict[str, Any]]:
        by_arch: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "correct": 0, "incorrect": 0, "unknown": 0})
        for m in self.metrics:
            d = by_arch[m.archetype]
            d["total"] += 1
            if m.final_is_correct is True:
                d["correct"] += 1
            elif m.final_is_correct is False:
                d["incorrect"] += 1
            else:
                d["unknown"] += 1

        out = []
        for archetype, d in sorted(by_arch.items(), key=lambda kv: (-kv[1]["total"], kv[0])):
            known = d["correct"] + d["incorrect"]
            out.append(
                {
                    "archetype": archetype,
                    **d,
                    "known": known,
                    "accuracy_when_known": (d["correct"] / known) if known else None,
                }
            )
        return out

    def archetype_outcome_lines(self) -> list[str]:
        rows = self.archetype_outcome_dict()
        if not rows:
            return ["n/a"]
        if all(r["known"] == 0 for r in rows):
            return ["No final-trial correctness labels found in TaskTrial."]

        arch_w = max(len("archetype"), max(len(r["archetype"]) for r in rows))
        total_w = max(len("total"), max(len(str(r["total"])) for r in rows))
        known_w = max(len("known"), max(len(str(r["known"])) for r in rows))
        correct_w = max(len("correct"), max(len(str(r["correct"])) for r in rows))
        incorrect_w = max(len("incorrect"), max(len(str(r["incorrect"])) for r in rows))
        unknown_w = max(len("unknown"), max(len(str(r["unknown"])) for r in rows))
        acc_w = max(len("acc"), 6)

        header = (
            f"{'archetype':<{arch_w}}  {'total':>{total_w}}  {'known':>{known_w}}  "
            f"{'acc':>{acc_w}}  {'correct':>{correct_w}}  {'incorrect':>{incorrect_w}}  {'unknown':>{unknown_w}}"
        )
        lines = [header]
        for r in rows:
            acc = r["accuracy_when_known"]
            acc_str = f"{acc*100:5.1f}%" if acc is not None else "n/a"
            lines.append(
                f"{r['archetype']:<{arch_w}}  {r['total']:>{total_w}}  {r['known']:>{known_w}}  "
                f"{acc_str:>{acc_w}}  {r['correct']:>{correct_w}}  {r['incorrect']:>{incorrect_w}}  {r['unknown']:>{unknown_w}}"
            )
        return lines


class _CircularGroups:
    def __init__(self):
        self.with_report: list[TaskTopologyMetrics] = []
        self.without_report: list[TaskTopologyMetrics] = []
        self.missing_annotation: list[TaskTopologyMetrics] = []

    def add(self, *, metrics: TaskTopologyMetrics, self_report_circular: Optional[bool]):
        if self_report_circular is None:
            self.missing_annotation.append(metrics)
        elif self_report_circular:
            self.with_report.append(metrics)
        else:
            self.without_report.append(metrics)

    def summary_lines(self) -> list[str]:
        n1 = len(self.with_report)
        n0 = len(self.without_report)
        nm = len(self.missing_annotation)
        n_annotated = n1 + n0
        if n_annotated == 0:
            return ["No post-task annotations found for the sampled tasks."]
        if n1 == 0:
            return [f"Annotated tasks: {n_annotated} (self-report yes=0, no={n0}); missing_annotation={nm}"]

        def mean(vals: list[float]) -> float:
            return sum(vals) / len(vals) if vals else 0.0

        def pull(metrics: list[TaskTopologyMetrics], attr: str) -> list[float]:
            return [float(getattr(m, attr)) for m in metrics]

        lines = [
            f"Annotated tasks: {n_annotated} (self-report yes={n1}, no={n0}); missing_annotation={nm}",
            f"Mean revisit_rate: {mean(pull(self.with_report, 'revisit_rate')):.3f} vs {mean(pull(self.without_report, 'revisit_rate')):.3f}",
            f"Mean scc_nodes_fraction: {mean(pull(self.with_report, 'scc_nodes_fraction')):.3f} vs {mean(pull(self.without_report, 'scc_nodes_fraction')):.3f}",
            f"Mean aba_backtrack_rate: {mean(pull(self.with_report, 'aba_backtrack_rate')):.3f} vs {mean(pull(self.without_report, 'aba_backtrack_rate')):.3f}",
            f"Mean serp_transition_rate: {mean(pull(self.with_report, 'serp_transition_rate')):.3f} vs {mean(pull(self.without_report, 'serp_transition_rate')):.3f}",
            f"Mean content_revisit_rate: {mean(pull(self.with_report, 'content_revisit_rate')):.3f} vs {mean(pull(self.without_report, 'content_revisit_rate')):.3f}",
            f"Mean content_scc_nodes_fraction: {mean(pull(self.with_report, 'content_scc_nodes_fraction')):.3f} vs {mean(pull(self.without_report, 'content_scc_nodes_fraction')):.3f}",
        ]
        return lines

    def summary_dict(self) -> dict[str, Any]:
        n1 = len(self.with_report)
        n0 = len(self.without_report)
        nm = len(self.missing_annotation)
        n_annotated = n1 + n0
        out: dict[str, Any] = {
            "counts": {
                "self_report_yes": n1,
                "self_report_no": n0,
                "annotated_total": n_annotated,
                "missing_annotation": nm,
            }
        }
        if n_annotated == 0:
            out["note"] = "No post-task annotations found for the sampled tasks."
            return out
        if n1 == 0:
            out["note"] = "No tasks with self-reported circular navigation in annotated subset."
            return out

        def mean(metrics: list[TaskTopologyMetrics], attr: str) -> float:
            return (
                sum(float(getattr(m, attr)) for m in metrics) / len(metrics)
                if metrics
                else 0.0
            )

        attrs = [
            "revisit_rate",
            "scc_nodes_fraction",
            "aba_backtrack_rate",
            "serp_transition_rate",
            "content_revisit_rate",
            "content_scc_nodes_fraction",
        ]
        out["means_yes_vs_no"] = {
            attr: {
                "yes": mean(self.with_report, attr),
                "no": mean(self.without_report, attr),
                "delta_yes_minus_no": mean(self.with_report, attr) - mean(self.without_report, attr),
            }
            for attr in attrs
        }
        return out


def _summ_line(label: str, values: list[float], *, unit: str) -> str:
    if not values:
        return f"{label}: n/a"
    values_sorted = sorted(values)
    mean_val = sum(values_sorted) / len(values_sorted)
    p50 = _percentile(values_sorted, 50)
    p25 = _percentile(values_sorted, 25)
    p75 = _percentile(values_sorted, 75)
    p90 = _percentile(values_sorted, 90)
    unit_suffix = f" {unit}" if unit else ""
    return (
        f"{label}: mean={mean_val:.3f}{unit_suffix}, median={p50:.3f}{unit_suffix}, "
        f"p90={p90:.3f}{unit_suffix}, IQR=[{p25:.3f}, {p75:.3f}]"
    )


def _metric_explanations_dict() -> dict[str, str]:
    return {
        "n_visits": "Total recorded page visits in the task (includes repeated visits).",
        "n_nodes": "Unique pages after normalization (SERPs are grouped by engine+query).",
        "n_edges": "Unique transitions between nodes (from visit sequence).",
        "n_unique_domains": "Number of unique domains visited.",
        "revisit_rate": "Fraction of visits that are repeats (1 - n_nodes/n_visits).",
        "aba_backtrack_rate": "How often the sequence does A→B→A (immediate backtracking).",
        "scc_nodes_fraction": "Fraction of nodes in a directed cycle in the visit-transition graph (SERP↔page cycles can inflate this).",
        "content_revisit_rate": "Revisit rate computed only on non-SERP pages (filters out normal SERP bouncing).",
        "content_aba_backtrack_rate": "A→B→A computed only when all three pages are non-SERP (filters out SERP back-and-forth).",
        "content_scc_nodes_fraction": "SCC fraction computed only on non-SERP transitions (cycles among content pages).",
        "reachable_fraction_from_root": "Fraction of nodes reachable from the first visited node using referrer edges (proxy for a coherent navigation tree).",
        "depth_max": "Max hop distance from the first node in the referrer graph (not the visit sequence).",
        "depth_p90": "90th-percentile hop distance from the first node in the referrer graph (not the visit sequence).",
        "branching_factor_mean": "Mean out-degree among nodes with at least one outgoing edge (how many distinct next-steps per node).",
        "hub_dominance": "Max out-degree normalized by (n_nodes-1); near 1 means one hub links to many nodes.",
        "serp_visits": "Number of SERP visits detected (Google/Bing/Baidu/DDG/Yahoo).",
        "serp_episode_fanout_mean": "Average number of unique non-SERP pages clicked per SERP episode.",
        "serp_return_rate": "Among SERP episodes with at least 1 click, fraction that return to a SERP later.",
        "serp_transition_rate": "Fraction of transitions where either side is a SERP (how SERP-centric the trajectory is).",
        "domain_entropy_norm": "0..1 diversity of domain visits (0=one domain, 1=even spread).",
        "dominant_visit_share": "Share of visits landing on the single most-visited node (often a SERP in hub-like search).",
        "dominant_is_serp": "Whether the most-visited node is a SERP node.",
        "final_is_correct": "Correctness of the last task trial when available.",
        "archetype": "Coarse label based on hub/chain/serp-loop signals (heuristic, meant for slicing + follow-up analysis).",
    }


def _archetype_explanations_dict() -> dict[str, str]:
    return {
        "degenerate": "Too few unique nodes to characterize (often 1 page or repeated same page).",
        "serp-hub": "A SERP acts as a central hub (many transitions involve SERP and it dominates out-links).",
        "hub-spoke": "Non-SERP hub links out to many distinct pages; returns may happen but one hub dominates.",
        "star": "Near pure hub-and-spoke without meaningful SERP involvement.",
        "chain": "Mostly linear progression with low branching (deep but not wide exploration).",
        "serp-hopping": "Multiple SERP episodes with returns to SERP after clicks (search-driven exploration).",
        "loop-heavy": "Cycles and backtracks among content pages (may indicate confusion or verification loops).",
        "mixed": "Doesn't strongly match the above heuristics; use metrics/archetype breakdown to slice further.",
    }


def _interpretation_notes() -> list[str]:
    return [
        "Content loop metrics (content_*) ignore SERP pages, so they focus on loops among content pages.",
        "High serp_transition_rate indicates SERP-centric browsing; high serp_return_rate indicates returning to SERP after clicks.",
        "In 'Outcome Slice', positive Δ(incorrect-correct) means the metric is higher for incorrect tasks (when labels exist).",
        "If self-report annotations are sparse, rely more on topology metrics and less on the self-report comparison block.",
    ]


@dataclass(frozen=True)
class _Stats:
    n: int
    mean: float
    median: float
    p25: float
    p75: float
    p90: float
    min: float
    max: float


def _stats(values: list[float]) -> Optional[_Stats]:
    if not values:
        return None
    values_sorted = sorted(values)
    n = len(values_sorted)
    mean_val = sum(values_sorted) / n
    return _Stats(
        n=n,
        mean=mean_val,
        median=_percentile(values_sorted, 50),
        p25=_percentile(values_sorted, 25),
        p75=_percentile(values_sorted, 75),
        p90=_percentile(values_sorted, 90),
        min=float(values_sorted[0]),
        max=float(values_sorted[-1]),
    )


def _stats_dict(values: list[float]) -> dict[str, Any]:
    s = _stats(values)
    if s is None:
        return {"n": 0}
    return {
        "n": s.n,
        "mean": s.mean,
        "median": s.median,
        "p25": s.p25,
        "p75": s.p75,
        "p90": s.p90,
        "min": s.min,
        "max": s.max,
    }


def _content_loop_metrics(keys: list[str], kinds: list[str]) -> tuple[float, float, float]:
    nonserp_positions = [i for i, k in enumerate(kinds) if k != "serp"]
    if not nonserp_positions:
        return 0.0, 0.0, 0.0

    content_visits = len(nonserp_positions)
    content_nodes = {keys[i] for i in nonserp_positions}
    content_revisit_rate = 1.0 - (len(content_nodes) / content_visits) if content_visits else 0.0

    content_aba = 0
    content_aba_den = 0
    for i in range(len(keys) - 2):
        if kinds[i] == "serp" or kinds[i + 1] == "serp" or kinds[i + 2] == "serp":
            continue
        content_aba_den += 1
        if keys[i] == keys[i + 2] and keys[i] != keys[i + 1]:
            content_aba += 1
    content_aba_backtrack_rate = content_aba / content_aba_den if content_aba_den else 0.0

    content_adj: dict[str, set[str]] = defaultdict(set)
    for i in range(len(keys) - 1):
        if kinds[i] == "serp" or kinds[i + 1] == "serp":
            continue
        a = keys[i]
        b = keys[i + 1]
        content_adj[a].add(b)

    if not content_nodes:
        return content_revisit_rate, content_aba_backtrack_rate, 0.0

    sccs = _strongly_connected_components(content_nodes, content_adj)
    scc_nodes = 0
    for comp in sccs:
        if len(comp) > 1:
            scc_nodes += len(comp)
    content_scc_nodes_fraction = scc_nodes / len(content_nodes) if content_nodes else 0.0

    return content_revisit_rate, content_aba_backtrack_rate, content_scc_nodes_fraction
