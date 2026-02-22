# dynamic_prompts_nodes.py
# Combined node file for Kaleidia Dynamic Prompt nodes
# - BaseDynamicPromptNode: shared logic (wildcards, YAML/TXT, recursion, repetition)
# - KN_DynamicPromptNode: random prompt node (unique-per-batch, seedable)
# - KN_SequentialPromptNode: sequential prompt node (S3 behavior: cycle N, step items)

import os
import sys
import random
import re
import json
import yaml
from pathlib import Path
from itertools import product
from .log_utils import logger

# use project folder_paths module (you said import folder_paths works)
import folder_paths

# ----------------------------
# Regex configuration
# ----------------------------
# Permissive but constrained wildcard regex:
# allows letters, digits, underscore, slash, asterisk, space and dash
# non-greedy to avoid over-capture when multiple wildcards appear in a single string
WILDCARD_RE = re.compile(r"__([A-Za-z0-9/*_ \-=,]+?)__")

# repetition block regex matches patterns like:
# Matches quantified random ranges like {1-3$$red|blue|green}
RANGE_RE = re.compile(r"\{(\d+)(?:-(\d+))?\$\$([^{}]+?)\}")

# Matches simple alternations like {a|b|c}
CHOICE_RE = re.compile(r"\{([^${}]+?\|[^${}]+?)\}")
# ----------------------------
# Base class - shared logic
# ----------------------------
class BaseDynamicPromptNode:
    """
    Shared dynamic prompt logic:
      - wildcard loading: YAML/JSON priority, TXT fallback (subfolder matching)
      - nested wildcard recursion with cycle & depth protection
      - repetition block parsing (inner expansions done inside-out)
      - flattening YAML nodes
      - helpers for splitting/joining
    This class is NOT itself a ComfyUI node; the two node classes below inherit it.
    """

    # wildcard folder is base_path/wildcards
    wildcard_folder = Path(folder_paths.base_path, "wildcards")

    # cache for parsed YAML/JSON files to avoid repeated disk reads
    _wildcard_cache = {}

    def __init__(self):
        # debugging: set instance.debug = True to enable console traces
        self.debug = False
        self._wildcard_cache = {}
        self.last_dir_mtime = 0
        if sys.platform == 'win32': os.system('')

    # -----------------------
    # Utility: flatten YAML/JSON node to list of strings
    # -----------------------
    def _flatten_data(self, data):
        """
        Recursively flatten a YAML/JSON node into a list of string leaves.
        - dict -> flatten values (preserves ordering of lists)
        - list -> flatten each element
        - str -> return as single element (stripped)
        - other -> stringified
        Output preserves original casing of values.
        """
        results = []
        if isinstance(data, dict):
            for v in data.values():
                results.extend(self._flatten_data(v))
        elif isinstance(data, list):
            for v in data:
                results.extend(self._flatten_data(v))
        elif isinstance(data, str):
            results.append(data.strip())
        else:
            results.append(str(data))
        return results

    #-----------------------
    # Resolve a basic prompt
    #-----------------------
    def resolve_prompt(self, template: str, max_depth: int = 10, joiner: str = ", ", seq_index: int = None, seq_depth_limit: int = 2, sequence_mode="Nested (Slow -> Fast)") -> str:
        """Iteratively resolves all dynamic elements (repetitions, choices, wildcards)."""
        text = template
        global_visited_tokens = set() 
        
        if os.path.exists(self.wildcard_folder):
            current_mtime = os.path.getmtime(self.wildcard_folder)
            if current_mtime > self.last_dir_mtime:
                self.wildcard_cache = {} # Wipe the RAM cache
                self.last_dir_mtime = current_mtime
                if self.debug: 
                    logger.warning("Clearing wildcard cache")
                    logger.warning(f"---------------------------------------------------------------")

        
        if self.debug: logger.debug(f"[Iterative] Starting resolution.")
            
        for depth in range(max_depth):
            
            # 1. Termination Check
            if not (WILDCARD_RE.search(text) or RANGE_RE.search(text) or CHOICE_RE.search(text)):
                if self.debug: logger.debug(f"[Iterative] Prompt fully resolved in {depth+1} steps.")
                return text

            # 2. Sequential vs Random Check
            # Only use Gear logic if within the sequential_passes limit
            is_seq_pass = (seq_index is not None and depth < seq_depth_limit)
            
            if self.debug: logger.debug(f"[Iterative] --- Pass {depth+1} ---")

            # --- A. Repetition Pass ({min-max$$...}) ---
            text = self._expand_repetition_blocks_iterative(text, set(), depth, joiner)
            
            # --- B. Expansion Pass ---
            if is_seq_pass:
                # Use the new Odometer method for top-level structure
                text, _ = self._expand_sequential_pass(text, depth, seq_index, sequence_mode="Nested (Slow -> Fast)")
            else:
                # Standard random behavior for deeper details
                text = self._expand_wildcards_one_level(text, global_visited_tokens, depth)
                text = self._expand_choice_blocks_basic(text)
            
        if self.debug: logger.warning(f"[Iterative] Max depth ({max_depth}) reached. Returning partial result.")
        return text
    
    def _expand_sequential_pass(self, text, depth, p_idx, sequence_mode="Nested (Slow -> Fast)"):
        import random
        matches = list(CHOICE_RE.finditer(text)) + list(WILDCARD_RE.finditer(text))
        if not matches: return text, 1

        matches.sort(key=lambda x: x.start()) # Nested Mode default
        current_text = text
        running_index = p_idx
        
        for match in matches:
            start, end = match.span()
            raw_match = match.group(0)
            
            # 1. Load options
            if raw_match.startswith("__"):
                path = match.group(1).split("=")[0].strip("_")
                options = self._load_category_wildcard(path)
            else:
                options, _ = self._parse_weighted_options(match.group(1).split("|"))

            if not options: continue
            opt_len = len(options)

            # --- 2. DYNAMIC NESTED GEAR LOGIC ---
            if sequence_mode == "Nested (Slow -> Fast)":
                if depth == 1:
                    # DYNAMIC SLOW GEAR: Shifts only when the current folder is exhausted
                    temp_idx = running_index
                    pick_idx = 0
                    current_weight = 1
                    
                    for i, opt in enumerate(options):
                        # Get real weight of the folder
                        weight = self._get_wildcard_count(opt.strip("_")) if opt.startswith("__") else 1
                        if temp_idx < weight:
                            pick_idx = i
                            current_weight = weight # Save this for the next depth
                            break
                        temp_idx -= weight
                    else:
                        pick_idx = 0 # Wrap around if index > total items
                    
                    mode_label = "DYN-CAT"
                else:
                    # DYNAMIC FAST GEAR: Uses the remainder of the index
                    # Note: For true precision, we'd pass the 'remainder' down, 
                    # but index % opt_len works for simple nested structures.
                    pick_idx = running_index % opt_len
                    mode_label = "DYN-SUB"
                
                pick_idx = pick_idx % opt_len
                do_break = True
            else:
                # FLAT MODE (Traditional Odometer)
                pick_idx = running_index % opt_len
                running_index //= opt_len 
                mode_label = "FLAT-SEQ"
                do_break = False

            # --- 3. REPLACEMENT & LOGGING ---
            chosen = str(options[pick_idx])
            if self.debug:
                print(f"{depth:<6} | {pick_idx:<4} | {opt_len:<5} | {mode_label:<10} | {raw_match[:30]}")

            current_text = current_text[:start] + chosen + current_text[end:]
            if do_break: break 

        return current_text, 1
        
    def _get_wildcard_count(self, path):
        # Use your existing logic to load the file, but just return len(options)
        options = self._load_category_wildcard(path)
        return len(options) if options else 1
        
    # Helper to check if a wildcard exists and load its options
    def _load_category_wildcard_for_expansion(self, token: str, visited: set) -> list[str]:
        """Loads options for a token, applying cycle check before loading."""
        norm_token = token.replace("\\", "/").strip("/")
        token_lower = norm_token.lower()

        if token_lower in visited:
            if self.debug: 
                # This is the expected output when a cycle is broken
                print(f"[Wildcard] Cycle token detected: {norm_token}") 
            return [] # Return empty list to signal a broken cycle

        visited.add(token_lower)
        return self._load_category_wildcard(norm_token) # Assumes _load_category_wildcard is an existing function

    def _expand_wildcards_one_level(self, text: str, global_visited_tokens: set, depth: int, seq_index: int = None) -> str:
        def replace_token(match):
            token_raw = match.group(1).strip()
            
            # 1. Standardize Path
            path = token_raw.split("=")[0] # Ignore anything after = for now
            norm_token = path.replace("\\", "/").strip("/")
            token_lower = norm_token.lower()
            
            # 2. Cycle Protection
            if token_lower in global_visited_tokens:
                return f"__{path}__"
            
            global_visited_tokens.add(token_lower)
            raw_options = self._load_category_wildcard(norm_token) 

            if not raw_options:
                global_visited_tokens.remove(token_lower)
                return f"__{path}__"

            # 3. Selection Logic
            available_options = list(raw_options)

            # --- Sequential Mode ---
            if seq_index is not None:
                chosen_option = available_options[seq_index % len(available_options)]
            
            # --- Random Mode with History ---
            else:
                # Filter out history if enabled
                if getattr(self, "use_history", False):
                    valid_options = [opt for opt in available_options if opt not in self.history]
                    # If all options were in history, reset to prevent dead-end
                    if not valid_options:
                        valid_options = available_options
                else:
                    valid_options = available_options

                chosen_option = random.choice(valid_options)

                # Save to History Sliding Window
                if getattr(self, "use_history", False):
                    self.history.append(chosen_option)
                    if len(self.history) > getattr(self, "history_limit", 3):
                        self.history.pop(0)

            global_visited_tokens.remove(token_lower)
            return str(chosen_option)

        return WILDCARD_RE.sub(replace_token, text)        
        
    # -----------------------
    # Core loader: hybrid YAML-first then TXT fallback
    # -----------------------
    def _load_category_wildcard(self, category_path, visited=None):
        """
        Load options for a wildcard path.
        Rules:
          - category_path: "pack/sub/file" or "fantasy/races/*"
          - Matching is case-insensitive for lookup (keys & relative paths),
            but returned values preserve original case.
          - YAML/JSON is searched first across all files; if any file yields results, use them.
            * YAML traversal uses case-insensitive key matching.
            * A node that is a dict at the final step is NOT considered a terminal match
              (per your YAML rules) unless '*' was used to flatten.
          - If YAML/JSON produced no results, fall back to TXT files located under wildcard_folder.
            * TXT matching uses relative path (POSIX style) compared case-insensitively.
            * If '*' is in the requested path, treat it as a prefix match (collect all files whose
              rel path starts with the prefix).
        - visited: set of lowered normalized category_path strings to avoid cycles
        Returns: list[str] of raw option strings (may contain nested wildcards to be resolved later)
        """
        if visited is None:
            visited = set()

        # normalize slashes but keep case and spaces
        category_path = category_path.replace("\\", "/").strip("/")
        cat_lower = category_path.lower()

        # cycle protection
        if cat_lower in visited:
            if self.debug:
                print(f"[Base] cycle detected for {category_path}; returning []")
            return []
        visited.add(cat_lower)

        options = []

        # ---------- YAML/JSON priority ----------
        parts = [p for p in category_path.split("/")]
        parts_lower = [p.lower() for p in parts]
        root_lower = parts_lower[0]
        rest_parts_lower = parts_lower[1:]

        # iterate over yaml/yml/json files under wildcard_folder recursively
        for ext in ("yaml", "yml", "json"):
            for f in self.wildcard_folder.rglob(f"*.{ext}"):
                # load & cache
                if f in self._wildcard_cache:
                    data = self._wildcard_cache[f]
                else:
                    try:
                        with open(f, "r", encoding="utf-8") as fh:
                            data = json.load(fh) if ext == "json" else yaml.safe_load(fh)
                    except Exception as e:
                        if self.debug:
                            print(f"[Base] Failed parse {f}: {e}")
                        data = None
                    self._wildcard_cache[f] = data

                if not data or not isinstance(data, dict):
                    continue

                # case-insensitive mapping of top-level keys to values
                data_lower = {k.lower(): v for k, v in data.items() if isinstance(k, str)}
                if root_lower not in data_lower:
                    continue

                # recursive traverse: use lowercased parts for matching keys
                def traverse(node, parts_left_lower):
                    # terminal: if no more parts to traverse
                    if not parts_left_lower:
                        # follow your rule: terminal only if node is list or scalar; dict is invalid terminal
                        if isinstance(node, list):
                            # Ensure all items from YAML are stripped and converted to string
                            return [str(item).strip() for item in self._flatten_data(node) if item is not None]
                        if isinstance(node, dict):
                            # invalid terminal; must specify subkey or use '*'
                            return []
                        return [str(node).strip()]
                    # we have more parts to go
                    part = parts_left_lower[0]
                    if part == "*":
                        # flatten subtree
                        return self._flatten_data(node)
                    if isinstance(node, dict):
                        node_lower = {k.lower(): v for k, v in node.items() if isinstance(k, str)}
                        if part in node_lower:
                            return traverse(node_lower[part], parts_left_lower[1:])
                    return []

                root_node = data_lower[root_lower]
                found = traverse(root_node, rest_parts_lower)
                if found:
                    if self.debug:
                        print(f"[Base] YAML {f} matched {category_path} -> {len(found)} items")
                    options.extend(found)
                else:
                    if self.debug:
                        print(f"[Base] YAML {f} no match for {category_path}")
                    
        # If YAML produced options, return them (YAML priority)
        if options!=[]:
            # NOTE: do not expand nested wildcards here; caller will call recursive expansion functions.
            return options

        # ---------- TXT fallback ----------
        # Compare relative path strings case-insensitively, but preserve original values
        cat_norm = category_path  # contains forward slashes
        cat_lower = cat_norm.lower()

        if "*" in cat_norm:
            # prefix matching: everything starting with prefix
            prefix_lower = cat_lower.split("*", 1)[0]
            if self.debug:
                print(f"[Base] TXT prefix lookup for: {prefix_lower}")
            for f in self.wildcard_folder.rglob("*.txt"):
                rel_path = f.relative_to(self.wildcard_folder).with_suffix("").as_posix()
                if rel_path.lower().startswith(prefix_lower):
                    with open(f, "r", encoding="utf-8") as fh:
                        # preserve original case/spacing in lines
                        options.extend([line.rstrip("\n") for line in fh if line.strip() != ""])
        else:
            if self.debug:
                print(f"[Base] TXT exact lookup for: {cat_lower}")
            for f in self.wildcard_folder.rglob("*.txt"):
                rel_path = f.relative_to(self.wildcard_folder).with_suffix("").as_posix()
                if rel_path.lower() == cat_lower:
                    with open(f, "r", encoding="utf-8") as fh:
                        options.extend([line.rstrip("\n") for line in fh if line.strip() != ""])

        if options!=[]:
            if self.debug:
                print(f"[Base] TXT matched {category_path} -> {len(options)} lines")
            return options

        # nothing found
        if self.debug:
            print(f"[Base] no match for wildcard: {category_path}")
        return []

    def _expand_repetition_blocks_iterative(self, text: str, current_visited: set, current_depth: int, joiner: str = ", ") -> str:
        """
        Expands repetition blocks by determining the count and joining the options. 
        It leaves remaining wildcards/choices for subsequent passes.
        """
        
        def replace_repetition(match):
            min_val = int(match.group(1))
            max_val_str = match.group(2)
            max_val = int(max_val_str) if max_val_str else min_val
            inner_raw = match.group(3)
            
            # 1. Resolve Inner Content for Options:
            # The inner content might be a simple choice block like "{apple|orange}"
            # or a single wildcard like "__fruit__".
            # We need to minimally resolve *only* the choices to get the options list.
            # This requires a call to the *simple* choice resolver.
            
            # Safety measure: Resolve simple inline choices first, if they exist.
            inner_content_with_choices_resolved = self._expand_choice_blocks_basic(inner_raw)
            
            # Split the content by pipe '|' to get the repeatable options.
            options = [opt.strip() for opt in inner_content_with_choices_resolved.split('|') if opt.strip()]

            if not options:
                 # If splitting failed or was empty, just return the raw inner part to avoid errors
                 return inner_raw 
            population, weights = self._parse_weighted_options(options)

            if not population:
                return inner_raw 
            
            # 3. Repetition Logic
            repetition_count = random.randint(min_val, max_val)
            
            # Select N options, using weights
            repeated_list = random.choices(population, weights=weights, k=repetition_count)          
            
            # Join the final parts with a comma and space
            return joiner.join(repeated_list)

        return RANGE_RE.sub(replace_repetition, text)# -----------------------
        
    def _parse_weighted_options(self, options_list: list[str]) -> tuple[list[str], list[int]]:
        """
        Parses a list of options, extracting weights (e.g., '2::red'). 
        Unweighted options default to a weight of 1.
        """
        population = []
        weights = []
        
        # Regex to find an optional leading weight: (weight)::(option)
        # OLD REGEX: r"(\d+)::(.*)" (Only integers)
        # NEW REGEX: r"([\d\.]+)::(.*)" (Allows digits and a decimal point)
        # Even better: r"(\d*\.?\d+)::(.*)" (Allows 1, 0.5, .5, 5.0)
        # We will use the simpler, slightly broader regex for flexibility:
        WEIGHT_RE = re.compile(r"([\d\.]+)::(.*)") # Match digits and optional period

        for raw_opt in options_list:
            match = WEIGHT_RE.match(raw_opt.strip())
            
            if match:
                # Weighted option found
                # ***CRITICAL CHANGE: Use float() instead of int()***
                weight = float(match.group(1)) 
                option = match.group(2).strip()
            else:
                # Unweighted option
                weight = 1.0 # Use float for consistency
                option = raw_opt.strip()       
                
            #if option:
            population.append(option)
            weights.append(weight)
                
        return population, weights        
            
    # Utility: expand choice blocks inside-out
    # -----------------------
    def _expand_choice_blocks_basic(self, text: str, tags = None) -> str:
        """Expands simple choice blocks, now with support for weights."""
        
        def replace_choice(match):
            raw_options = [o.strip() for o in match.group(1).split("|")]
            
            if not raw_options:
                return ""

            if tags:
                # Look for options that either:
                # 1. Literally contain the tag
                # 2. Are wildcards (which might contain the tag deeper down)
                valid_options = [ o for o in raw_options if any(t in o.lower() for t in tags) or "__" in o ]
            
                # If we found valid paths, only pick from those
                if valid_options:
                    raw_options = valid_options
                
            # 1. Parse weights and options
            population, weights = self._parse_weighted_options(raw_options)

            if not population:
                return ""

            # 2. Make the weighted choice
            chosen_option = random.choices(population, weights=weights, k=1)[0]
            return chosen_option

        return CHOICE_RE.sub(replace_choice, text)
        
# ----------------------------
# KN_DynamicPromptNode (Random)
# ----------------------------
class KN_DynamicPromptNode(BaseDynamicPromptNode):
    """
    Random dynamic prompt node.
    - Always random selection from expanded possibilities.
    - Optionally unique-per-batch (no duplicates during the same ComfyUI batch run).
    - Supports seeding for deterministic runs.
    """
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "template": ("STRING", {
                    "default": "A {happy|sad} __videogamechars/male__ with {1-3$$__color__}",
                    "multiline": True,
                    "dynamicPrompts": False,
                }),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                "join_style": (["space", "period", "comma", "and"], {"default": "period", "tooltip": "A connector for repetitive prompt parts. Defaults to '. '. Example 3 colors: red. blue. yellow. or with and option: red and blue and yellow"}),
                "use_history": ("BOOLEAN", {"default": False, "tooltip": "Prevents the same wildcard option from being picked twice until history is cleared."}),
                "clear_history": ("BOOLEAN", {"default": False, "tooltip": "Wipes the history of used options for this session."}),
                "history_limit": ("INT", {"default": 3, "min": 1, "max": 100, "tooltip": "How many previous choices to remember and avoid."}),
                "debug": ("BOOLEAN", {"default": False, "tooltip": "Gives debug output to the console about the processing of the dynamic prompt. Default is false to not spam the console."}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("Prompt",)
    FUNCTION = "generate"
    CATEGORY = "KaleidiaNodes/PromptNodes"

    def __init__(self):
        super().__init__()
        self.history = []  # Persistent across generations
        self.history_limit = 3
        self.use_history = False        # track used outputs during a ComfyUI run -> ensures uniqueness per batch
        self._used_this_batch = set()
        self.last_template = None

    def generate(self, template, seed=-1, join_style="period", use_history=False, clear_history=False, history_limit=3, debug=False):
        """
        Generate a single prompt (random).
        Steps:
          - optionally seed RNG
          - reset per-batch used set if template changed (and reset_on_change)
          - expand repetition blocks (basic random behavior)
          - expand nested wildcards into all possible expansions
          - pick one, enforcing uniqueness if requested
        """
        # basic state sanity
        self.debug = debug
        self.use_history = use_history
        self.history_limit = history_limit

        if clear_history:
            self.history.clear()
            
        # seed RNG if requested
        if seed >= 0:
            random.seed(seed)
        else:
            random.seed()
      
        # map joiner dropdown
        join_map = {"space": " ", "period": ". ", "comma": ", ", "and": " and "}
        joiner = join_map.get(join_style, ". ")
           
        if self.debug:
            logger.debug("---------------------------------------------------------------")
            logger.debug(f"[KN_DynamicPromptNode] Start processing of prompt: {template}")
            
        choice = self.resolve_prompt(template, joiner=joiner)
        
        if self.debug:
            logger.debug(f"[KN_DynamicPromptNode] Selected end prompt: {choice}")
            logger.debug(f"---------------------------------------------------------------")

        return (choice,)

# ----------------------------
# KN_SequentialPromptNode (Sequential, S3+D)
# ----------------------------
class KN_SequentialPromptNode(BaseDynamicPromptNode):
    _global_index = 0
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "template": ("STRING", {"default": "", "multiline": True}),
                "sequence_mode": (["Nested (Slow -> Fast)", "Flat (Fast -> Slow)"],),
                "sequential_passes": ("INT", {"default": 2, "min": 1, "max": 5}),
                "index_offset": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff, "tooltip": "Adds to the internal counter to shift the starting point."}),
                "join_style": (["space", "period", "comma", "and"], {"default": "period"}),
                "reset_counter": ("BOOLEAN", {"default": False}),
                "debug": ("BOOLEAN", {"default": False}),
            }
        }

    RETURN_TYPES = ("STRING",)
    FUNCTION = "generate"
    CATEGORY = "KaleidiaNodes/PromptNodes"

    @classmethod
    def IS_CHANGED(cls, **kwargs): return cls._global_index

    def generate(self, template, sequential_passes=2, index_offset=0, join_style="period", reset_counter=False, debug=False, sequence_mode="Nested (Slow -> Fast)"):
        if reset_counter: KN_SequentialPromptNode._global_index = 0
        self.debug = debug
        join_map = {"space": " ", "period": ". ", "comma": ", ", "and": " and "}
        joiner = join_map.get(join_style, ". ")
        
        # Use our counter + user offset
        current_idx = KN_SequentialPromptNode._global_index + index_offset
        
        if self.debug:
            logger.debug(f"---------------------------------------------------------------")
            logger.debug(f"[KN_SequentialPromptNode] Start processing of prompt: {template}")
            logger.debug(f"[KN_SequentialPromptNode] Start processing with index: {current_idx}")
            
        # Resolve prompt using the sequential index
        # We pass current_idx down to _expand_wildcards_one_level
        prompt = self.resolve_prompt(template, joiner=joiner, seq_index=current_idx, seq_depth_limit=sequential_passes, sequence_mode=sequence_mode)
        
        # Increment for the next generation
        KN_SequentialPromptNode._global_index += 1
        
        if self.debug:
            logger.debug(f"[KN_SequentialPromptNode] Selected end prompt: {prompt}")
            logger.debug(f"[KN_SequentialPromptNode] Next sequential index: {KN_SequentialPromptNode._global_index}")
            logger.debug(f"---------------------------------------------------------------")
            
        return (prompt, current_idx)
# End of dynamic_prompts_nodes.py
