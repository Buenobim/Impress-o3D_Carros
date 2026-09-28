# Gera o modelo, a plaquinha de teste e o projeto fatiado para a Bambu A1 mini.
# Uso (PowerShell, na pasta do repositorio):  .\gerar_tudo.ps1

$ErrorActionPreference = "Stop"
$blender = "C:\Program Files\Blender Foundation\Blender 5.0\blender.exe"
$bambu   = "C:\Program Files\Bambu Studio\bambu-studio.exe"
Set-Location $PSScriptRoot

Write-Host "1/3 Modelando o Gol no Blender (sem abrir a interface)..."
& $blender -b --factory-startup -P gol_kitcard.py | Select-String "CARTAO|STL|AVISO|OK|Error"

Write-Host "2/3 Gerando a plaquinha de teste de folgas..."
& $blender -b --factory-startup -P teste_folgas.py | Select-String "teste_folgas|Error"

Write-Host "3/3 Fatiando no Bambu Studio (A1 mini, PLA Basic, 0.20 mm, 4 cores)..."
Push-Location saida
& $bambu --slice 0 --arrange 0 --assemble `
  --load-settings "../bambu_cfg/machine.json;../bambu_cfg/process.json" `
  --load-filaments "../bambu_cfg/f1.json;../bambu_cfg/f2.json;../bambu_cfg/f3.json;../bambu_cfg/f4.json" `
  --load-filament-ids "1,2,3,4" `
  --outputdir . --export-3mf gol_kitcard_A1mini.3mf `
  gol_card_1_vermelho.stl gol_card_2_preto.stl gol_card_3_prata.stl gol_card_4_branco.stl | Out-Null
Pop-Location
Write-Host "Pronto: saida\gol_kitcard_A1mini.3mf"
