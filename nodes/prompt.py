# raw GPT output, unfixed and untested!
import random
import re
import folder_paths
from pathlib import Path
import os
from itertools import product

class DynamicPromptNode:
    """
    Dynamic prompt generator with:
    - Inline random options {option1|option2|...}
    - Wildcards from ComfyUI wildcards folder: __filename__
    - Nested placeholders
    - Sequential combinatorial output with optional reset on template change
    """
    
    #wildcard_folder = os.path.join(folder_paths.base_path)
    wildcard_folder = Path(folder_paths.base_path,"wildcards")
    combinatorial_index = 0
    last_template = None

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "template": ("STRING", {"default": "A {happy|sad} __subjects__ with __adjective__","multiline": True, "dynamicPrompts": True}),
                "seed": ("INT", {"default": -1}),
                "mode": (["random", "sequential"], {"default": "random"}),
                "reset_on_change": ("BOOL", {"default": True}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("Prompt",)
    FUNCTION = "generate"
    CATEGORY = "KaleidiaNodes/PromptNodes"

    def generate(self, template, seed=-1, mode="random", reset_on_change=True):
        if seed >= 0:
            random.seed(seed)
        else:
            random.seed()

        # Reset combinatorial index if template changed and option enabled
        if reset_on_change and template != self.last_template:
            self.combinatorial_index = 0
            self.last_template = template

        if mode == "random":
            # Recursive random replacement
            def resolve(text, depth=0):
                if depth > 20:
                    return text

                def replace_inline(match):
                    options = [opt.strip() for opt in match.group(1).split("|")]
                    choice = random.choice(options)
                    return resolve(choice, depth + 1)

                text = re.sub(r"\{([^{}]+)\}", replace_inline, text)

                def replace_wildcard(match):
                    filename = match.group(1).strip()
                    file_path = self.wildcard_folder / f"{filename}.txt"
                    if file_path.exists():
                        with open(file_path, "r", encoding="utf-8") as f:
                            lines = [line.strip() for line in f if line.strip()]
                        if lines:
                            choice = random.choice(lines)
                            return resolve(choice, depth + 1)
                    return f"__{filename}__"

                text = re.sub(r"__([A-Za-z0-9_]+)__", replace_wildcard, text)
                return text

            return (resolve(template),)

        elif mode == "sequential":
            # Parse template into placeholders
            placeholder_pattern = r"\{([^{}]+)\}|__([A-Za-z0-9_]+)__"
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
                    filename = match.group(2).strip()
                    file_path = self.wildcard_folder / f"{filename}.txt"
                    if file_path.exists():
                        with open(file_path, "r", encoding="utf-8") as f:
                            options = [line.strip() for line in f if line.strip()]
                    else:
                        options = [f"__{filename}__"]

                tokens.append(None)
                option_lists.append(options)

            tokens.append(template[last_index:])

            if not option_lists:
                return (template,)

            # Compute combination for current index
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

            return (prompt,)

        return ("<invalid mode>",)


# Register node
# NODE_CLASS_MAPPINGS.update({"DynamicPromptNode": DynamicPromptNode})
# NODE_DISPLAY_NAME_MAPPINGS.update({"DynamicPromptNode": "Dynamic Prompt Generator"})
