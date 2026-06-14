# notebook_proteina_complexa

Proteina Complexaを実施するためのJupyter Notebookです。  
Google Colabを使ってブラウザ上で実行できます。ローカル環境の構築は不要です。

## ノートブックを開く

以下のボタンをクリックすると、Google Colab上でノートブックが開きます。

> **👇 ここをクリックしてください**
>
> [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ShintaroMinami/notebook_proteina_complexa/blob/main/proteina_complexa.ipynb)

## 事前準備

### 1. Googleアカウント

Google Colabの利用にはGoogleアカウントが必要です。  
まだお持ちでない場合は、[Googleアカウントの作成ページ](https://accounts.google.com/signup)から作成してください。

### 2. Google Colabについて

Google Colab（正式名称: Google Colaboratory）は、**ブラウザ上で様々なプログラムを実行できるGoogleの無料サービス**です。

- ここで公開されているノートブックは、上記の「Open In Colab」ボタンをクリックするとGoogle Colab上で開きます。
- ノートブックはテキストセル(説明が書かれた区画)とコードセル(プログラムが書かれた区画)を組み合わせて作成されており、コードセルを実行するとPythonコードが動作して、その結果がセルの下に表示されます。
- 計算はインターネット上のGoogleのコンピュータで行われるため、お使いのPCへのインストールは不要で、PCに負荷もかかりません。
- ボタンをクリックした際にGoogleアカウントへのログインを求められた場合は、ログインしてください。
- 無料版では、保存できるデータ量や利用できる計算資源（GPUの種類や連続利用時間など）に制限があります。

### 3. ノートブックの実行方法

1. ボタンをクリックしてノートブックを開きます
2. 画面上部のメニューから **「ランタイム」→「すべてのセルを実行」** を選択するか、各セルを上から順に**実行ボタン**（セル左側の ▶ ）で実行してください
3. 初回実行時に「このノートブックはGitHubで作成されたものです」という警告が表示されることがありますが、**「このまま実行」** を選択してください

> **⚠️ 注意:** ノートブック上での変更はColabのセッション終了時に失われます。結果を残したい場合は、次のいずれかを行ってください。
> - **最終セル「5. 結果のダウンロード」** を実行すると、デザインPDB・予測構造・スコアCSVなどの全結果がzipにまとめられ、お使いのPCにダウンロードされます。
> - ノートブック自体を残したい場合は、**「ファイル」→「ドライブにコピーを保存」** でGoogleドライブに保存してください。

## References

本ノートブックは以下のツール・手法を利用しています。

- **Proteina-Complexa**
  Didi, K., Zhang, Z., Zhou, G. *et al.* Scaling Atomistic Protein Binder Design with Generative Pretraining and Test-Time Compute. *arXiv* (2026). https://arxiv.org/abs/2603.27950
  GitHub: https://github.com/NVIDIA-Digital-Bio/Proteina-Complexa
- **AlphaFold2**
  Jumper, J., Evans, R., Pritzel, A. *et al.* Highly accurate protein structure prediction with AlphaFold. *Nature* **596**, 583–589 (2021). https://doi.org/10.1038/s41586-021-03819-2
- **Boltz-1**
  Wohlwend, J., Corso, G., Passaro, S. *et al.* Boltz-1: Democratizing Biomolecular Interaction Modeling. *bioRxiv* (2024). https://doi.org/10.1101/2024.11.19.624167
- **Boltz-2**
  Passaro, S., Corso, G., Wohlwend, J. *et al.* Boltz-2: Towards Accurate and Efficient Binding Affinity Prediction. *bioRxiv* (2025). https://doi.org/10.1101/2025.06.14.659707
- **ipSAE**
  Dunbrack, R. L. Rēs ipSAE loquuntur: What's wrong with AlphaFold's ipTM score and how to fix it. *bioRxiv* (2025). https://doi.org/10.1101/2025.02.10.637595
- **ColabDesign**
  Ovchinnikov, S. *et al.* *ColabDesign: Making Protein Design accessible to all via Google Colab.* GitHub: https://github.com/sokrypton/ColabDesign
- **py3Dmol / 3Dmol.js**
  Rego, N. & Koes, D. 3Dmol.js: molecular visualization with WebGL. *Bioinformatics* **31**, 1322–1324 (2015). https://doi.org/10.1093/bioinformatics/btu829
