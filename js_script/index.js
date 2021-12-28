import { parse } from 'node-html-parser'
import fetch from 'node-fetch'

var channelID = process.argv[2];

const response = await fetch(`https://youtube.com/channel/${channelID}/live`)
const text = await response.text()
const html = parse(text)
const canonicalURLTag = html.querySelector('link[rel=canonical]')
const canonicalURL = canonicalURLTag.getAttribute('href')
const isStreaming = canonicalURL.includes('/watch?v=')

if (isStreaming == true) {
  console.log(canonicalURL)
} else {
  console.log(isStreaming)
}