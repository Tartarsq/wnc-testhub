from throughput_test import ThroughputTester


def main() -> None:
    try:
        tester = ThroughputTester(
            speedtest_executable="speedtest.exe",
            timeout_seconds=180,
        )

        results = tester.run_full_test()

        print("\n" + "=" * 45)
        print("SPEEDTEST RESULTS")
        print("=" * 45)

        print(
            f"Download: "
            f"{results['download_mbps']} Mbps"
        )

        print(
            f"Upload: "
            f"{results['upload_mbps']} Mbps"
        )

        print(
            f"Ping: "
            f"{results['ping_ms']} ms"
        )

        print(
            f"Jitter: "
            f"{results['ping_jitter_ms']} ms"
        )

        print(
            f"Packet loss: "
            f"{results['packet_loss_percent']}%"
        )

        print(
            f"ISP: "
            f"{results['isp']}"
        )

        print(
            f"External IP: "
            f"{results['external_ip']}"
        )

        print(
            f"Interface: "
            f"{results['interface_name']}"
        )

        print(
            f"Server: "
            f"{results['server_name']}, "
            f"{results['server_location']}"
        )

        print(
            f"Result URL: "
            f"{results['result_url']}"
        )

    except (FileNotFoundError, RuntimeError) as error:
        print(f"\nTest failed:\n{error}")


if __name__ == "__main__":
    main()