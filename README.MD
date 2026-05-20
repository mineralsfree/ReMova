During the preparation of this work, the author used Claude Code (Anthropic, claude-opus-4-7) to assist in writing the data cleaning pipeline. The AI tool was used for generating initial pipeline structure, writing tests, benchmarks and implementing some of the features. All AI-generated code was reviewed, tested, and modified by the author as needed. The author takes full responsibility for the correctness, design decisions, and content of the submitted pipeline.
All data used during development was handled in accordance with the University of Oslo's data regulations. No sensitive or personal data was entered into the AI tool.

# Pipeline for fixing, filtering and deduplicating of Belarusian datasets

### Prerequisites:

- Download glotLID model weights:
```
wget -O glotlid.bin -P models/ https://huggingface.co/cis-lmu/glotlid/resolve/main/model_v3.bin?download=true
```
