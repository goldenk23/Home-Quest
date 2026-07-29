import { TopToolbar } from '@/components/editor/top-toolbar'
import { SideRail } from '@/components/editor/side-rail'
import { ToolPanel } from '@/components/editor/tool-panel'
import { CanvasArea } from '@/components/editor/canvas-area'
import { StatusBar } from '@/components/editor/status-bar'

export default function Page() {
  return (
    <main className="flex h-dvh flex-col overflow-hidden">
      <TopToolbar />
      <div className="flex min-h-0 flex-1">
        <SideRail />
        <ToolPanel />
        <CanvasArea />
      </div>
      <StatusBar />
    </main>
  )
}
