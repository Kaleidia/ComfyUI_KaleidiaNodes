import random
import re
from pathlib import Path
from itertools import product
import json
import yaml
import folder_paths

WILDCARD_RE = re.compile(r"__(.+?)__")

class KN_DynamicPromptNode:
    """
    Dynamic prompt generator with:
    - Inline random options {option1|option2|...}
    - Wildcards from ComfyUI wildcards folder: __category/subcategory__ or __category/*__
    - Sequential combinatorial output
    - Optional reset_on_change
    - Cached YAML/JSON wildcard loading for performance
    """

    # Updated wildcard folder
    wildcard_folder = Path(folder_paths.base_path, "wildcards")

    # Cache for parsed YAML/JSON files: {filename: parsed_data}
    _wildcard_cache = {}

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "template": ("STRING", {
                    "default": "A {happy|sad} __videogamechars/male__ with __adjective__",
                    "multiline": True,
                    "dynamicPrompts": True
                }),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                "mode": (["random", "sequential"], {"default": "random"}),
                "reset_on_change": ("BOOLEAN", {"default": True}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("Prompt",)
    FUNCTION = "generate"
    CATEGORY = "KaleidiaNodes/PromptNodes"

    # -----------------------
    # Instance state
    # -----------------------
    def _ensure_state(self):
        if not hasattr(self, "combinatorial_index"):
            self.combinatorial_index = 0
            self.last_template = None

    def generate(self, template, seed=-1, mode="random", reset_on_change=True):
        self._ensure_state()

        if seed >= 0:
            random.seed(seed)
        else:
            random.seed()

        if reset_on_change and template != self.last_template:
            self.combinatorial_index = 0
            self.last_template = template

        if mode == "random":
            return (self._resolve_random(template),)
        elif mode == "sequential":
            return (self._resolve_sequential(template),)
        return ("<invalid mode>",)

    # -----------------------
    # Random / Sequential
    # -----------------------
    def _resolve_random(self, text, depth=0):
        if depth > 20:
            return text

        # inline {a|b|c}
        def replace_inline(match):
            options = [opt.strip() for opt in match.group(1).split("|")]
            random.shuffle(options)
            choice = random.choice(options)
            return self._resolve_random(choice, depth + 1)

        text = re.sub(r"\{([^{}]+)\}", replace_inline, text)

        # wildcards __category/subcategory__ or __category/*__
        def replace_wildcard(match):
            path = match.group(1).strip()
            options = self._load_category_wildcard(path)
            if options:
                random.shuffle(options)
                choice = random.choice(options)
                return self._resolve_random(choice, depth + 1)
            return f"__{path}__"

        text = re.sub(r"__([A-Za-z0-9_/*]+)__", replace_wildcard, text)
        return text

    def _resolve_sequential(self, template):
        placeholder_pattern = r"\{([^{}]+)\}|__([A-Za-z0-9_/*]+)__"
        tokens = []
        matches = list(re.finditer(placeholder_pattern, template))
        last_index = 0
        option_lists = []

        for match in matches:
            start, end = match.span()
            tokens.append(template[last_index:start])
            last_index = end

            if match.group(1):
                options = [opt.strip() for opt in match.group(1).split("|")]
            else:
                path = match.group(2).strip()
                options = self._load_category_wildcard(path)
                if not options:
                    options = [f"__{path}__"]

            tokens.append(None)
            option_lists.append(options)

        tokens.append(template[last_index:])

        if not option_lists:
            return template

        all_combinations = list(product(*option_lists))
        combo_index = self.combinatorial_index % len(all_combinations)
        self.combinatorial_index += 1

        selected_combo = all_combinations[combo_index]
        prompt = ""
        combo_idx = 0
        for tok in tokens:
            if tok is None:
                prompt += selected_combo[combo_idx]
                combo_idx += 1
            else:
                prompt += tok

        return prompt

    # -----------------------
    # Wildcard helpers
    # -----------------------
    def _flatten_data(self, data):
        results = []
        if isinstance(data, dict):
            for v in data.values():
                results.extend(self._flatten_data(v))
        elif isinstance(data, list):
            for v in data:
                results.extend(self._flatten_data(v))
        elif isinstance(data, str):
            results.append(data.strip())
        return results


    def _load_category_wildcard(self, category_path, visited=None):
        """
        Resolve a wildcard path (TXT/YAML/JSON) into a list of strings.
        Supports:
          - TXT subfolder files: __characters/fantasy/male__
          - TXT wildcards with * prefix: __characters/fantasy/*__
          - YAML/JSON categories: __videogamechars/male__
          - YAML/JSON with *: __fantasy/races/*__
        Returns a flat list of expanded options.
        """
        if visited is None:
            visited = set()
        cat_lower = category_path.lower()

        # cycle check
        if cat_lower in visited:
            return []
        visited = set(visited)
        visited.add(cat_lower)

        options = []

        # -------------------------
        # 1) TXT files
        # -------------------------
        if "*" in category_path:
            prefix = cat_lower.split("*", 1)[0]
            for f in self.wildcard_folder.rglob("*.txt"):
                rel_path = f.relative_to(self.wildcard_folder).with_suffix("")
                rel_str = rel_path.as_posix().lower()
                if rel_str.startswith(prefix):
                    with open(f, "r", encoding="utf-8") as fh:
                        options.extend([line.strip() for line in fh if line.strip()])
        else:
            for f in self.wildcard_folder.rglob("*.txt"):
                rel_path = f.relative_to(self.wildcard_folder).with_suffix("")
                rel_str = rel_path.as_posix().lower()
                if rel_str == cat_lower:
                    with open(f, "r", encoding="utf-8") as fh:
                        options.extend([line.strip() for line in fh if line.strip()])

        if options:
            return self._resolve_recursive_options(options, visited)

        # -------------------------
        # 2) YAML / JSON files
        # -------------------------
        parts = [p.lower() for p in category_path.split("/")]
        root = parts[0]
        rest_parts = parts[1:]

        def traverse_node(node, parts_left):
            if not parts_left:
                return self._flatten_data(node)
            part = parts_left[0]
            if part == "*":
                return self._flatten_data(node)
            if isinstance(node, dict):
                node_lower = {k.lower(): v for k, v in node.items() if isinstance(k, str)}
                if part in node_lower:
                    return traverse_node(node_lower[part], parts_left[1:])
            return []

        for ext in ("yaml", "yml", "json"):
            for f in self.wildcard_folder.rglob(f"*.{ext}"):
                if f in self._wildcard_cache:
                    data = self._wildcard_cache[f]
                else:
                    try:
                        with open(f, "r", encoding="utf-8") as fh:
                            data = json.load(fh) if ext == "json" else yaml.safe_load(fh)
                    except Exception:
                        data = None
                    self._wildcard_cache[f] = data

                if not data or not isinstance(data, dict):
                    continue

                data_lower = {k.lower(): v for k, v in data.items() if isinstance(k, str)}
                if root not in data_lower:
                    continue

                yaml_options = traverse_node(data_lower[root], rest_parts)
                if yaml_options:
                    options.extend(yaml_options)

        return self._resolve_recursive_options(options, visited)


    def _resolve_recursive_options(self, options, visited):
        """Expand nested wildcards inside option strings recursively."""
        resolved_all = []
        for opt in options:
            expanded = self._expand_option_with_wildcards(opt, visited)
            resolved_all.extend(expanded)
        return resolved_all


    def _expand_option_with_wildcards(self, opt, visited, depth=0, max_depth=10):
        """
        Expand an option string with nested __wildcards__.
        Produces all combinations (cartesian product) if multiple wildcards in one string.
        Handles both TXT (folder-based) and YAML/JSON wildcards.
        """
        if depth >= max_depth:
            return [opt]

        if not WILDCARD_RE.search(opt):
            return [opt]

        parts = re.split(WILDCARD_RE, opt)
        literal_parts = parts[0::2]
        token_names = parts[1::2]

        list_of_token_options = []
        for token in token_names:
            token_lower = token.lower()
            if token_lower in visited:
                # cycle → leave placeholder
                list_of_token_options.append([f"__{token}__"])
                continue

            # load options for this token (TXT or YAML/JSON)
            inner_opts = self._load_category_wildcard(token, visited=visited | {token_lower})
            if not inner_opts:
                list_of_token_options.append([f"__{token}__"])
            else:
                # ensure nested TXT expansions are also fully resolved
                inner_resolved = self._resolve_recursive_options(inner_opts, visited | {token_lower})
                list_of_token_options.append(inner_resolved)

        expanded_results = []
        for combo in product(*list_of_token_options):
            text = ""
            for i, lit in enumerate(literal_parts):
                text += lit
                if i < len(combo):
                    text += combo[i]

            if WILDCARD_RE.search(text):
                # recurse into deeper nested wildcards
                sub_expanded = self._expand_option_with_wildcards(
                    text, visited=visited, depth=depth + 1, max_depth=max_depth
                )
                expanded_results.extend(sub_expanded)
            else:
                expanded_results.append(text)

        return expanded_results
