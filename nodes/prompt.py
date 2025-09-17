import random
import re
from pathlib import Path
from itertools import product
import json
import yaml
import folder_paths


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
                "seed": ("INT", {"default": -1}),
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
            choice = random.choice(options)
            return self._resolve_random(choice, depth + 1)

        text = re.sub(r"\{([^{}]+)\}", replace_inline, text)

        # wildcards __category/subcategory__ or __category/*__
        def replace_wildcard(match):
            path = match.group(1).strip()
            options = self._load_category_wildcard(path)
            if options:
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

    def _load_category_wildcard(self, category_path):
        if "/" in category_path:
            root, subcat = category_path.split("/", 1)
        else:
            root, subcat = category_path, None

        root = root.lower()
        subcat = subcat.lower() if subcat else None

        options = []

        # TXT file
        txt_file = self.wildcard_folder / f"{category_path}.txt"
        if txt_file.exists():
            with open(txt_file, "r", encoding="utf-8") as f:
                options.extend([line.strip() for line in f if line.strip()])

        # YAML / JSON files
        for ext in ("yaml", "yml", "json"):
            for f in self.wildcard_folder.glob(f"*.{ext}"):
                if f in self._wildcard_cache:
                    data = self._wildcard_cache[f]
                else:
                    with open(f, "r", encoding="utf-8") as fh:
                        if ext == "json":
                            data = json.load(fh)
                        else:
                            data = yaml.safe_load(fh)
                    self._wildcard_cache[f] = data

                if not data:
                    continue

                # make root keys lowercase for case-insensitive match
                data_lower = {k.lower(): v for k, v in data.items() if isinstance(k, str)}

                if root in data_lower:
                    node = data_lower[root]

                    # lowercase subcategory mapping if dict
                    if isinstance(node, dict):
                        node_lower = {k.lower(): v for k, v in node.items() if isinstance(k, str)}
                        if subcat == "*" or subcat is None:
                            options.extend(self._flatten_data(node_lower))
                        elif subcat in node_lower:
                            options.extend(self._flatten_data(node_lower[subcat]))
                    else:
                        # if node is list or str at root
                        options.extend(self._flatten_data(node))

        return options