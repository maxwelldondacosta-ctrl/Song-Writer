import { Editor } from '@/components/editor/editor'

export default async function SongEditorPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params
  return <Editor slug={slug} />
}
