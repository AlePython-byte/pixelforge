# medir.ps1 - Corre los experimentos de PixelForge y guarda los datos crudos
# en carga/resultados/ (JSON y CSV de k6 + CSV de docker stats).
#
# Uso, desde la carpeta del proyecto y con Docker Desktop encendido:
#   powershell -ExecutionPolicy Bypass -File .\medir.ps1
#   powershell -ExecutionPolicy Bypass -File .\medir.ps1 -Solo escalado
#   (opciones de -Solo: todo, specs, escalado, rampa, memoria)
#
# Experimentos:
#   specs    -> especificaciones de la maquina fisica y de la VM de Docker
#   escalado -> misma carga (10 usuarios, 4 min) con 1, 2 y 4 CPU
#   rampa    -> 10, 25, 50 y 100 usuarios con 1 CPU hasta encontrar el quiebre
#   memoria  -> /subir con peticiones simultaneas hasta el OOM killer (512 MB)
param(
  [ValidateSet('todo', 'specs', 'escalado', 'rampa', 'memoria')]
  [string]$Solo = 'todo'
)

$ErrorActionPreference = 'Continue'
$Raiz = $PSScriptRoot
$Res = Join-Path $Raiz 'carga\resultados'
New-Item -ItemType Directory -Force -Path $Res | Out-Null
Set-Location $Raiz

function Sello { Get-Date -Format 'yyyy-MM-ddTHH-mm-ss' }

function Esperar-Api {
  Write-Host '  Esperando a que la API responda...'
  for ($i = 0; $i -lt 90; $i++) {
    try {
      $r = Invoke-WebRequest -Uri 'http://localhost:8000/salud' -UseBasicParsing -TimeoutSec 3
      if ($r.StatusCode -eq 200) { Write-Host '  API lista.'; return }
    } catch { }
    Start-Sleep -Seconds 2
  }
  Write-Host '  ERROR: la API no respondio en 3 minutos.' -ForegroundColor Red
}

function Levantar-Api([string]$Cpus, [string]$Mem = '512m') {
  $env:API_CPUS = $Cpus
  $env:API_MEM_LIMIT = $Mem
  Write-Host "  Levantando API con $Cpus CPU y $Mem de RAM..."
  docker compose up -d api | Out-Null
  Esperar-Api
  Start-Sleep -Seconds 5
}

function Estado-Api {
  $id = docker compose ps --all -q api
  return (docker inspect -f '{{.State.Status}} OOMKilled={{.State.OOMKilled}} ExitCode={{.State.ExitCode}}' $id)
}

# docker stats en segundo plano: una muestra de todos los contenedores
# cada ~2 s (lo que tarda docker stats --no-stream) hasta que se detenga.
function Iniciar-Stats([string]$Archivo) {
  'hora,contenedor,cpu_pct,mem_uso,mem_pct,red_io,disco_io,pids' | Out-File -FilePath $Archivo -Encoding ascii
  return Start-Job -ArgumentList $Archivo -ScriptBlock {
    param($Archivo)
    while ($true) {
      $hora = Get-Date -Format 'o'
      $lineas = docker stats --no-stream --format '{{.Name}},{{.CPUPerc}},{{.MemUsage}},{{.MemPerc}},{{.NetIO}},{{.BlockIO}},{{.PIDs}}'
      foreach ($l in $lineas) { Add-Content -Path $Archivo -Value "$hora,$l" -Encoding ascii }
    }
  }
}

function Detener-Stats($Job) {
  Stop-Job $Job | Out-Null
  Remove-Job $Job | Out-Null
}

function Correr-K6([string]$Etiqueta, [string]$Script, [string[]]$Extra = @()) {
  Write-Host "  Corriendo k6: $Etiqueta" -ForegroundColor Yellow
  $stats = Iniciar-Stats (Join-Path $Res "$($Etiqueta)_stats.csv")
  Start-Sleep -Seconds 4   # algunas muestras en reposo antes de la carga
  $argumentos = @('compose', '--profile', 'carga', 'run', '--rm', '-e', "ETIQUETA=$Etiqueta", 'k6', 'run') +
    $Extra + @('--out', "csv=/carga/resultados/$($Etiqueta)_k6.csv", $Script)
  & docker @argumentos
  Start-Sleep -Seconds 4
  Detener-Stats $stats
}

function Exp-Specs {
  Write-Host '== Especificaciones de la maquina ==' -ForegroundColor Cyan
  $f = Join-Path $Res 'especificaciones_maquina.txt'
  "Especificaciones de la maquina fisica - $(Get-Date -Format o)" | Out-File $f -Encoding ascii
  Get-CimInstance Win32_Processor |
    Select-Object Name, NumberOfCores, NumberOfLogicalProcessors, MaxClockSpeed, L2CacheSize, L3CacheSize |
    Format-List | Out-File $f -Append -Encoding ascii
  Get-CimInstance Win32_ComputerSystem |
    Select-Object Manufacturer, Model, @{ n = 'RAM_GB'; e = { [math]::Round($_.TotalPhysicalMemory / 1GB, 1) } } |
    Format-List | Out-File $f -Append -Encoding ascii
  Get-CimInstance Win32_PhysicalMemory | Select-Object Capacity, Speed |
    Format-Table -AutoSize | Out-File $f -Append -Encoding ascii
  Get-PhysicalDisk | Select-Object FriendlyName, MediaType, BusType, @{ n = 'GB'; e = { [math]::Round($_.Size / 1GB) } } |
    Format-Table -AutoSize | Out-File $f -Append -Encoding ascii
  'Docker Desktop (maquina virtual Linux):' | Out-File $f -Append -Encoding ascii
  docker info --format 'CPUs={{.NCPU}} Memoria={{.MemTotal}} Kernel={{.KernelVersion}} SO={{.OperatingSystem}}' |
    Out-File $f -Append -Encoding ascii
  Get-Content $f
}

function Exp-Escalado {
  foreach ($c in @('1', '2', '4')) {
    Write-Host "== Escalado: $c CPU, 10 usuarios, 4 min ==" -ForegroundColor Cyan
    Levantar-Api $c
    Correr-K6 "escalado_cpu$($c)_$(Sello)" '/carga/humo.js' @('--vus', '10', '--duration', '4m')
  }
}

function Exp-Rampa {
  Write-Host '== Rampa hasta el quiebre: 1 CPU, 10 -> 25 -> 50 -> 100 usuarios ==' -ForegroundColor Cyan
  Levantar-Api '1'
  Correr-K6 "rampa_cpu1_$(Sello)" '/carga/rampa.js'
}

function Exp-Memoria {
  Write-Host '== Memoria: /subir hasta el OOM killer (512 MB) ==' -ForegroundColor Cyan
  Levantar-Api '1' '512m'
  $et = "memoria_cpu1_512m_$(Sello)"
  Correr-K6 $et '/carga/memoria.js'
  $log = Join-Path $Res "$($et)_estado.txt"
  'Estado de la API despues de la rampa de memoria (mediana.jpg, 2 a 16 peticiones simultaneas):' | Out-File $log -Encoding ascii
  (Estado-Api) | Out-File $log -Append -Encoding ascii
  docker compose logs --tail 30 api 2>&1 | Out-File $log -Append -Encoding ascii
  Write-Host "  Estado tras la rampa de memoria: $(Estado-Api)"

  Write-Host '== Memoria: una sola peticion con grande.jpg (8000x8000) ==' -ForegroundColor Cyan
  Levantar-Api '1' '512m'
  $stats = Iniciar-Stats (Join-Path $Res "$($et)_grande_stats.csv")
  Start-Sleep -Seconds 4
  $resp = curl.exe -s -m 120 -w ' HTTP=%{http_code} tiempo=%{time_total}s' -X POST -F 'archivo=@imagenes_prueba/grande.jpg' http://localhost:8000/subir
  Start-Sleep -Seconds 4
  Detener-Stats $stats
  '' | Out-File $log -Append -Encoding ascii
  'Una sola peticion /subir con grande.jpg (8000x8000):' | Out-File $log -Append -Encoding ascii
  "Respuesta: $resp" | Out-File $log -Append -Encoding ascii
  (Estado-Api) | Out-File $log -Append -Encoding ascii
  Write-Host "  Respuesta: $resp"
  Write-Host "  Estado: $(Estado-Api)"
}

Write-Host 'PixelForge - experimentos de carga' -ForegroundColor Green
docker info *> $null
if ($LASTEXITCODE -ne 0) {
  Write-Host 'Docker Desktop no esta encendido. Abrelo y espera "Engine running".' -ForegroundColor Red
  exit 1
}
if (-not (Test-Path (Join-Path $Raiz 'imagenes_prueba\grande.jpg'))) {
  Write-Host 'Faltan las imagenes de prueba; generandolas...'
  docker compose up -d api | Out-Null
  Esperar-Api
  docker compose exec api python imagenes_prueba/generar.py
}
docker compose up -d db | Out-Null
$inicio = Get-Date

switch ($Solo) {
  'specs' { Exp-Specs }
  'escalado' { Exp-Escalado }
  'rampa' { Exp-Rampa }
  'memoria' { Exp-Memoria }
  'todo' { Exp-Specs; Exp-Escalado; Exp-Rampa; Exp-Memoria }
}

# Dejar la API como estaba: 1 CPU y 512 MB.
Levantar-Api '1' '512m'
Remove-Item Env:API_CPUS, Env:API_MEM_LIMIT -ErrorAction SilentlyContinue
$min = [math]::Round(((Get-Date) - $inicio).TotalMinutes, 1)
Write-Host "Listo en $min minutos. Los datos quedaron en carga\resultados\" -ForegroundColor Green
