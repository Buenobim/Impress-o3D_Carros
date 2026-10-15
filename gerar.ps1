# Gera um carro do zero: perfis oficiais -> modelo + cartao (Blender) -> fatiamento verificado.
# Uso (PowerShell, na raiz do repositorio):
#   .\gerar.ps1 gol_1980
#   .\gerar.ps1 puma_gts
#   .\gerar.ps1 cupom          (cupom de calibracao, comum a todos os carros)
# Para em qualquer falha (perfil, malha, cartao, cupom ou G-code).
param([Parameter(Mandatory = $true)][string]$carro)

$ErrorActionPreference = "Stop"
$blender = "C:\Program Files\Blender Foundation\Blender 5.0\blender.exe"
$env:PYTHONIOENCODING = "utf-8"
Set-Location $PSScriptRoot

function Step($msg, $block) {
    Write-Host $msg
    & $block
    if ($LASTEXITCODE -ne 0) { throw "FALHOU: $msg" }
}

Step "1/3 Perfis oficiais da A1 mini (inherits + include)..." { python bambu_perfis.py }
if ($carro -eq "cupom") {
    Step "2/3 Cupom de calibracao..." { & $blender -b --factory-startup --python-exit-code 1 -P calibracao/cupom.py | Select-String "CUPOM|Error" }
} else {
    if (-not (Test-Path "carros\$carro\modelo.py")) { throw "nao existe carros\$carro\modelo.py" }
    Step "2/3 Modelo + cartao + validacao das malhas ($carro)..." {
        & $blender -b --factory-startup --python-exit-code 1 -P kitcard/gerar.py -- $carro | Select-String "CARTAO|linha|arquivo|FALHOU|ALTO|Error|^OK"
    }
}
Step "3/3 Fatiamento e verificacao do G-code..." { python fatiar.py $carro }
Write-Host "Pronto."
