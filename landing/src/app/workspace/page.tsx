export default function WorkspacePage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-gray-50 px-6">
      <div className="max-w-md text-center">
        <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-indigo-100 text-3xl">
          🎵
        </div>
        <h1 className="text-3xl font-bold tracking-tight text-gray-900 mb-3">
          Welcome to Eurydice
        </h1>
        <p className="text-gray-600 mb-8">
          Your workspace is ready. Start practicing, explore repertoire, or
          connect with your teacher.
        </p>
        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <a
            href="/"
            className="inline-flex items-center justify-center rounded-lg border border-gray-300 bg-white px-5 py-2.5 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50"
          >
            ← Back to Home
          </a>
        </div>
      </div>
    </main>
  );
}
