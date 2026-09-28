# Gera tudo: perfis oficiais -> modelo -> cupom -> fatiamento verificado.
# Uso (PowerShell, na pasta do repositorio):  .\gerar_tudo.ps1
# Para em qualquer falha (perfil, malha, cupom ou G-code).

$ErrorActionPreference = "Stop"
$blender = "C:\Program Files\Blender Foundation\Blender 5.0\blender.exe"
Set-Location $PSScriptRoot

function Step($msg, $block) {
    Write-Host $msg
    & $block
    if ($LASTEXITCODE -ne 0) { throw "FALHOU: $msg" }
}

Step "1/4 Perfis oficiais da A1 mini (inherits + include)..." { python bambu_perfis.py }
Step "2/4 Modelo do Gol + cartao + validacao das malhas..." { & $blender -b --factory-startup -P gol_kitcard.py | Select-String "CARTAO|arquivo|FALHOU|Error|^OK" }
Step "3/4 Cupom de calibracao..." { & $blender -b --factory-startup -P teste_folgas.py | Select-String "CUPOM|Error" }
Step "4/4 Fatiamento e verificacao do G-code..." { python fatiar.py }
Remove-Item saida\*.blend1 -ErrorAction SilentlyContinue
Write-Host "Pronto. Resultados em saida\ (ver saida\fatiamento.json)."
