export const longUrl = `https://example.com/${'langer-pfad-'.repeat(35)}bericht`
export const longIdentifier = 'UnunterbrochenerDateiname'.repeat(35)
export const originalCode = `def beschreibung():\n    text = "${'Lange Codezeile ohne Änderung des Inhalts. '.repeat(24)}"\n    return text\n`

export const strengthTable = `| Stärke | Bedeutung |
| --- | --- |
| Klarheit | Auch ausführliche deutsche Beschreibungen bleiben vollständig innerhalb der verfügbaren Chatbreite lesbar. |
| Ausdauer | Lange Antworten werden automatisch umgebrochen und lassen sich weiterhin vollständig markieren und kopieren. |`

export const fiveColumnTable = `| Stärke | Bedeutung | Link | Inline-Code | Datei |
| --- | --- | --- | --- | --- |
| Ausdauer | ${'Eine ausführliche Beschreibung mit natürlichem Zeilenumbruch. '.repeat(6)} | [${longUrl}](${longUrl}) | \`${longIdentifier}\` | ${longIdentifier} |
| Klarheit | Erste Textzeile mit weiteren Worten, die innerhalb derselben Tabellenzelle auf mehrere sichtbare Zeilen umbrechen. | [Bericht](${longUrl}) | \`wert = 42\` | bericht.txt |`

export const overflowMarkdown = `# Vollständig lesbare Antworten

${strengthTable}

${fiveColumnTable}

## Lange Texte und verschachtelte Listen

${longIdentifier}

[${longUrl}](${longUrl}) und \`${longIdentifier}\`

- Erste Ebene
  - Zweite Ebene mit ${longIdentifier}
    - Dritte Ebene mit [${longUrl}](${longUrl})

> Ein Zitat mit \`${longIdentifier}\`.

\`\`\`python
${originalCode}\`\`\`

\`\`\`${longIdentifier}
${'nicht_hervorgehoben'.repeat(100)}
\`\`\`

${'Ein weiterer Absatz erhält die natürliche Lesebreite auch in sehr langen Antworten.\n\n'.repeat(25)}`
