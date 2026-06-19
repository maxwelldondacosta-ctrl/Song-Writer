'use client'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { TabVocab } from './tab-vocab'
import { TabSuno } from './tab-suno'
import { TabRhymes } from './tab-rhymes'
import { TabCadence } from './tab-cadence'
import { TabNotes } from './tab-notes'
import type { Song } from '@/types/song'

export function RightRail({ song }: { song: Song }) {
  return (
    <Tabs defaultValue="vocab" className="w-full">
      <TabsList className="grid grid-cols-5 w-full">
        <TabsTrigger value="vocab">Vocab</TabsTrigger>
        <TabsTrigger value="rhymes">Rhymes</TabsTrigger>
        <TabsTrigger value="cadence">Cadence</TabsTrigger>
        <TabsTrigger value="suno">Suno</TabsTrigger>
        <TabsTrigger value="notes">Notes</TabsTrigger>
      </TabsList>
      <TabsContent value="vocab"><TabVocab song={song} /></TabsContent>
      <TabsContent value="rhymes"><TabRhymes song={song} /></TabsContent>
      <TabsContent value="cadence"><TabCadence song={song} /></TabsContent>
      <TabsContent value="suno"><TabSuno song={song} /></TabsContent>
      <TabsContent value="notes"><TabNotes notes={song.notes} /></TabsContent>
    </Tabs>
  )
}
