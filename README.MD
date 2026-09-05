During the preparation of this work, the author used Claude Code (Anthropic, claude-opus-4-7) to assist in writing the data cleaning pipeline. The AI tool was used for generating initial pipeline structure, writing tests, benchmarks and implementing some of the features. All AI-generated code was reviewed, tested, and modified by the author as needed. The author takes full responsibility for the correctness, design decisions, and content of the submitted pipeline.
All data used during development was handled in accordance with the University of Oslo's data regulations. No sensitive or personal data was entered into the AI tool.

# Pipeline for fixing, filtering and deduplicating of Belarusian datasets

### Prerequisites:

- Download glotLID model weights:
```
wget -O glotlid.bin -P models/ https://huggingface.co/cis-lmu/glotlid/resolve/main/model_v3.bin?download=true
```

- Build LanguageTool with `LocalChecker`:

The `languagetool` stage spawns `org.languagetool.server.LocalChecker`, which is
not in stock LanguageTool — it lives in
<https://github.com/mineralsfree/languagetool>. `configs/pipeline.yaml` includes
that stage, so the pipeline will not start without a local build of it.

```
git clone git@github.com:mineralsfree/languagetool.git
cd languagetool/languagetool-server
mvn -am -DskipTests package
mvn dependency:build-classpath -Dmdep.outputFile=target/cp.txt
printf -- '-cp %s:%s' "$(cat target/cp.txt)" \
    "$PWD/target/languagetool-server-6.9-SNAPSHOT.jar" > target/localchecker.argfile
```

Then point `command:` in `configs/pipeline.yaml` at the argfile.
