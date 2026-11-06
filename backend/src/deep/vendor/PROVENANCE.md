# Retinexformer upstream

The architecture is vendored **unmodified** from
https://github.com/caiyuanhao1998/Retinexformer/blob/master/basicsr/models/archs/RetinexFormer_arch.py
on 2026-11-06. GitHub's commit API was rate-limited, so this snapshot is pinned by content hash:

`SHA256 1567c89d55285a3c1a4d4ca33f288b1fd98dc6b6bbdf971eda02d745f9087631`

Upstream copyright: Yuanhao Cai, 2023. The original MIT license is in LICENSE.txt.
The official LOL-v1 YAML is retained alongside the architecture. Its inference configuration is
`in_channels=3, out_channels=3, n_feat=40, stage=1, num_blocks=[1,2,2]`.

Official checkpoint folder, linked by the upstream README:
https://drive.google.com/drive/folders/1ynK5hfQachzc8y96ZumhkPPDXzHJwaQV

Use `LOL_v1.pth`. Architecture licensing does not establish licenses for training datasets
or every upstream checkpoint. Review those terms for your intended use. No benchmark or
model-quality claims are implied by synthetic tests.
