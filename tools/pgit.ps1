# Appelle git.exe depuis un run Paperclip sous Windows.
#
# Le runtime Paperclip exporte GIT_AUTHOR_NAME, GIT_AUTHOR_EMAIL,
# GIT_COMMITTER_NAME, GIT_COMMITTER_EMAIL et GIT_ASKPASS en chaînes VIDES. Une
# variable d'environnement vide n'est pas ignorée par Git : elle écrase la
# configuration du dépôt, donc tout `git commit` échoue sur
# « fatal: empty ident name (for <>) not allowed ». Le profil bash du launcher
# Paperclip fait ce nettoyage (`if [ -z "$GIT_AUTHOR_NAME" ]; then unset ...`),
# mais PowerShell ne lit pas ce profil.
#
# Ce wrapper supprime ces variables vides pour l'appel, puis passe la main à
# git.exe. L'identité retombe donc sur user.name / user.email du dépôt, et les
# identifiants GitHub viennent du credential helper configuré dans
# .git/config (voir README, section « Git / GitHub depuis un run Paperclip »).
#
# Usage :  pwsh tools/pgit.ps1 commit -m "..."     (ou powershell -File)

foreach ($name in 'GIT_AUTHOR_NAME', 'GIT_AUTHOR_EMAIL', 'GIT_COMMITTER_NAME', 'GIT_COMMITTER_EMAIL', 'GIT_ASKPASS') {
    # GetEnvironmentVariable rend $null pour une variable absente comme pour une
    # variable vide ; les deux cas doivent aboutir à « absente ». Passer par .NET
    # plutôt que par le provider Env:, qui traite mal les valeurs vides
    # (Test-Path rend $true mais Get-Item lève ItemNotFoundException).
    # Une identité réellement renseignée reste prioritaire.
    if (-not [Environment]::GetEnvironmentVariable($name)) {
        [Environment]::SetEnvironmentVariable($name, $null)
    }
}

& git.exe @args
exit $LASTEXITCODE
