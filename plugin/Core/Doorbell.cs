using System;
using System.Runtime.InteropServices;

namespace SilkTronPlugin;

/// <summary>
/// One direction of a wake-up signal between the game and the Python trainer, backed by a
/// named pipe (FIFO) that the Python side creates. The data itself stays in shared memory;
/// the pipe only carries single bytes so the waiting side can block instead of polling.
/// </summary>
public class Doorbell : IDisposable
{
    private const int O_RDWR = 2;
    private const int O_NONBLOCK = 0x800;
    private const short POLLIN = 1;

    [StructLayout(LayoutKind.Sequential)]
    private struct PollFd
    {
        public int fd;
        public short events;
        public short revents;
    }

    [DllImport("libc", SetLastError = true)]
    private static extern int open(string path, int flags);

    [DllImport("libc", SetLastError = true)]
    private static extern int close(int fd);

    [DllImport("libc", SetLastError = true)]
    private static extern IntPtr read(int fd, byte[] buf, IntPtr count);

    [DllImport("libc", SetLastError = true)]
    private static extern IntPtr write(int fd, byte[] buf, IntPtr count);

    [DllImport("libc", SetLastError = true)]
    private static extern int poll(ref PollFd fds, uint nfds, int timeout);

    private readonly byte[] ringBuffer = { 1 };
    private readonly byte[] drainBuffer = new byte[64];
    private int fd;

    private Doorbell(int fd)
    {
        this.fd = fd;
    }

    /// <summary>
    /// Opens the FIFO at the given path, or returns null if it doesn't exist.
    /// </summary>
    public static Doorbell Open(string path)
    {
        // O_RDWR keeps the open from blocking until the other side connects, and means reads
        // never see EOF if the other process exits.
        int fd = open(path, O_RDWR | O_NONBLOCK);
        if (fd < 0)
        {
            Plugin.Logger.LogWarning($"Could not open doorbell {path} (errno {Marshal.GetLastWin32Error()}), falling back to polling");
            return null;
        }

        Plugin.Logger.LogInfo($"Opened doorbell {path}");
        return new Doorbell(fd);
    }

    public void Ring()
    {
        // If the pipe is full, the other side already has wake-ups pending, so EAGAIN is fine.
        write(fd, ringBuffer, (IntPtr)1);
    }

    /// <summary>
    /// Blocks until the doorbell rings or the timeout expires. Returns true if it rang.
    /// </summary>
    public bool Wait(int timeoutMs)
    {
        var pollFd = new PollFd { fd = fd, events = POLLIN };
        if (poll(ref pollFd, 1, timeoutMs) <= 0 || (pollFd.revents & POLLIN) == 0)
        {
            return false;
        }

        while ((long)read(fd, drainBuffer, (IntPtr)drainBuffer.Length) > 0)
        {
        }
        return true;
    }

    public void Dispose()
    {
        if (fd >= 0)
        {
            close(fd);
            fd = -1;
        }
    }
}
