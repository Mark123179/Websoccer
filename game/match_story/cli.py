import json, sys, os
from .narrator import narrate
from . import render

def main(paths, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    for p in paths:
        export = json.load(open(p, encoding='utf-8'))
        res = narrate(export)
        base = os.path.splitext(os.path.basename(p))[0]
        md = render.to_markdown(res)
        open(os.path.join(out_dir, f"drehbuch_{base}.md"), 'w', encoding='utf-8').write(md)
        json.dump(render.to_json(res), open(os.path.join(out_dir, f"story_{base}.json"), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(base, res['score'], 'Zeilen', len(res['lines']), 'Issues', len(res['issues']))

if __name__ == '__main__':
    main(sys.argv[1:-1], sys.argv[-1])
